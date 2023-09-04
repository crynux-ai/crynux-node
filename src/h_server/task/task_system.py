import logging
from typing import Dict, Optional, Type, TypeVar

from anyio import Event, create_task_group, fail_after, get_cancelled_exc_class, sleep
from anyio.abc import TaskGroup

from h_server.event_queue import EventQueue
from h_server.models import TaskEvent

from .exceptions import TaskError
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
    ) -> None:
        self._state_cache = state_cache
        self._queue = queue
        self._retry_delay = retry_delay
        self._distributed = distributed

        self._tg: Optional[TaskGroup] = None
        self._stop_event: Optional[Event] = None

        self._runners: Dict[int, TaskRunner] = {}

        self._runner_cls: Type[TaskRunner] = InferenceTaskRunner

    def set_runner_cls(self, runner_cls: Type[TaskRunner]):
        self._runner_cls = runner_cls

    @property
    def event_queue(self) -> EventQueue:
        return self._queue

    async def start(self):
        assert self._stop_event is None, "The TaskSystem has already been started."
        assert self._tg is None, "The TaskSystem has already been started."

        self._stop_event = Event()

        try:
            async with create_task_group() as tg:
                self._tg = tg
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
                            task_name="sd_lora_inference",
                            distributed=self._distributed,
                        )
                        await runner.init()
                        self._runners[task_id] = runner
                        _logger.debug(f"Create task runner for {event.task_id}")

                    async def _process_event(ack_id: int, event: TaskEvent):
                        try:
                            finished = await runner.process_event(event)
                            with fail_after(5, shield=True):
                                if finished:
                                    del self._runners[task_id]
                                    await self._state_cache.delete(task_id)
                                    _logger.debug(f"Task {event.task_id} finished")
                                await self.event_queue.ack(ack_id)
                                _logger.debug(
                                    f"Task {event.task_id} process event {event.kind} success."
                                )
                        except get_cancelled_exc_class() as e:
                            with fail_after(5, shield=True):
                                await self.event_queue.no_ack(ack_id)
                            raise e
                        except TaskError as e:
                            _logger.error(
                                f"Task {event.task_id} process event {event.kind} failed."
                            )
                            if e.retry:
                                with fail_after(self._retry_delay + 5, shield=True):
                                    _logger.debug(f"Retry {event} for {event.task_id}")
                                    await sleep(self._retry_delay)
                                    await self.event_queue.no_ack(ack_id=ack_id)
                        except Exception as e:
                            _logger.exception(e)
                            _logger.error(
                                f"Task {event.task_id} process event {event.kind} unknown error."
                            )
                            with fail_after(5, shield=True):
                                await self.event_queue.no_ack(ack_id)

                    tg.start_soon(_process_event, ack_id, event)
        except get_cancelled_exc_class() as e:
            raise
        except Exception as e:
            _logger.exception(e)
            raise
        finally:
            self._tg = None
            self._stop_event = None

    def stop(self):
        assert self._stop_event is not None, "The TaskSystem has not been started."
        assert self._tg is not None, "The TaskSystem has not been started."
        self._stop_event.set()
        if not self._tg.cancel_scope.cancel_called:
            self._tg.cancel_scope.cancel()

    async def has_task(self, task_id: int) -> bool:
        if task_id in self._runners:
            return True
        return await self._state_cache.has(task_id)

    async def is_running(self) -> bool:
        if len(self._runners) > 0:
            return True
        n = await self._state_cache.count(deleted=False)
        return n > 0


_default_task_system: Optional[TaskSystem] = None


def get_task_system() -> TaskSystem:
    assert _default_task_system is not None, "TaskSystem has not been set."

    return _default_task_system


def set_task_system(task_system: TaskSystem):
    global _default_task_system

    _default_task_system = task_system
