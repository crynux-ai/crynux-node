import logging
from typing import Dict, Optional, Type, TypeVar

from anyio import Event, create_task_group, fail_after, get_cancelled_exc_class, sleep
from anyio.abc import TaskGroup

from h_server.event_queue import EventQueue
from h_server.models import TaskEvent, TaskStatus

from .state_cache import TaskStateCache
from .task_runner import InferenceTaskRunner, TaskRunner

_logger = logging.getLogger(__name__)


T = TypeVar("T", bound=TaskRunner)


class TaskSystem(object):
    def __init__(
        self,
        state_cache: TaskStateCache,
        queue: EventQueue,
        distributed: bool = False,
        retry_delay: float = 5,
        task_name: str = "sd_lora_inference",
    ) -> None:
        self._state_cache = state_cache
        self._queue = queue
        self._retry_delay = retry_delay
        self._distributed = distributed
        self._task_name = task_name

        self._tg: Optional[TaskGroup] = None
        self._stop_event: Optional[Event] = None

        self._runners: Dict[int, TaskRunner] = {}

        self._runner_cls: Type[TaskRunner] = InferenceTaskRunner

    def set_runner_cls(self, runner_cls: Type[TaskRunner]):
        self._runner_cls = runner_cls

    @property
    def state_cache(self) -> TaskStateCache:
        return self._state_cache

    @property
    def event_queue(self) -> EventQueue:
        return self._queue

    async def _recover(self):
        running_status = [TaskStatus.Pending, TaskStatus.Executing, TaskStatus.ResultUploaded, TaskStatus.Disclosed]
        running_states = await self.state_cache.find(status=running_status)
        for state in running_states:
            runner = self._runner_cls(
                task_id=state.task_id,
                state_cache=self._state_cache,
                queue=self._queue,
                task_name=self._task_name,
                distributed=self._distributed,
            )
            runner.state = state
            self._runners[state.task_id] = runner
            _logger.debug(f"Recreate task runner for {state.task_id}")


    async def start(self):
        assert self._stop_event is None, "The TaskSystem has already been started."
        assert self._tg is None, "The TaskSystem has already been started."

        self._stop_event = Event()

        try:
            async with create_task_group() as tg:
                self._tg = tg
                await self._recover()
                while not self._stop_event.is_set():
                    ack_id, event = await self.event_queue.get()
                    task_id = event.task_id
                    if task_id in self._runners:
                        runner = self._runners[task_id]
                    else:
                        runner = self._runner_cls(
                            task_id=task_id,
                            state_cache=self._state_cache,
                            queue=self._queue,
                            task_name=self._task_name,
                            distributed=self._distributed,
                        )
                        valid = await runner.init()
                        if valid:
                            self._runners[task_id] = runner
                            _logger.debug(f"Create task runner for {event.task_id}")
                        else:
                            _logger.debug(
                                f"Cannot process event {event.kind} of task {event.task_id}."
                                " Perhaps the task has finished by error."
                            )
                            continue

                    async def _process_event(ack_id: int, event: TaskEvent):
                        try:
                            finished = await runner.process_event(event)
                            with fail_after(5, shield=True):
                                if finished:
                                    del self._runners[task_id]
                                    _logger.debug(f"Task {event.task_id} finished")
                                await self.event_queue.ack(ack_id)
                                _logger.debug(
                                    f"Task {event.task_id} process event {event.kind} success."
                                )
                        except get_cancelled_exc_class():
                            with fail_after(5, shield=True):
                                await self.event_queue.no_ack(ack_id)
                            raise
                        except Exception:
                            _logger.debug(f"Task {event.task_id} process event {event.kind} failed.")
                            with fail_after(5, shield=True):
                                await self.event_queue.no_ack(ack_id=ack_id)
                                del self._runners[task_id]
                            raise

                    tg.start_soon(_process_event, ack_id, event)
        except get_cancelled_exc_class():
            raise
        except Exception as e:
            _logger.exception(e)
            raise
        finally:
            self._tg = None
            self._stop_event = None

    def stop(self):
        if self._stop_event is not None:
            self._stop_event.set()
        if self._tg is not None and not self._tg.cancel_scope.cancel_called:
            self._tg.cancel_scope.cancel()


_default_task_system: Optional[TaskSystem] = None


def get_task_system() -> TaskSystem:
    assert _default_task_system is not None, "TaskSystem has not been set."

    return _default_task_system


def set_task_system(task_system: TaskSystem):
    global _default_task_system

    _default_task_system = task_system
