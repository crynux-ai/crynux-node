import logging
from typing import Dict, Optional, Type, TypeVar

from anyio import create_task_group, get_cancelled_exc_class
from anyio.abc import TaskGroup
from tenacity import AsyncRetrying, before_sleep_log, wait_exponential

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
        retry: bool = True,
        task_name: str = "sd_lora_inference",
    ) -> None:
        self._state_cache = state_cache
        self._queue = queue
        self._retry = retry
        self._distributed = distributed
        self._task_name = task_name

        self._tg: Optional[TaskGroup] = None

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

    async def _run_task(self, task_id: int):
        async def _inner():
            runner = self._runners[task_id]
            try:
                await runner.run()
            except get_cancelled_exc_class():
                raise
            except Exception as e:
                _logger.exception(e)
                _logger.error(f"Task {task_id} error: {str(e)}")
                raise
            finally:
                del self._runners[task_id]

        if self._retry:
            async for attemp in AsyncRetrying(
                wait=wait_exponential(multiplier=10),
                before_sleep=before_sleep_log(_logger, logging.ERROR, exc_info=True),
                reraise=True,
            ):
                with attemp:
                    await _inner()
        else:
            await _inner()

    async def _recover(self, tg: TaskGroup):
        running_status = [
            TaskStatus.Pending,
            TaskStatus.Executing,
            TaskStatus.ResultUploaded,
            TaskStatus.Disclosed,
        ]
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
            tg.start_soon(self._run_task, state.task_id)
            _logger.debug(f"Recreate task runner for {state.task_id}")

    async def start(self):
        assert self._tg is None, "The TaskSystem has already been started."

        try:
            async with create_task_group() as tg:
                self._tg = tg
                await self._recover(tg)
                while True:
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
                        self._runners[task_id] = runner
                        tg.start_soon(self._run_task, task_id)

                    await runner.send(ack_id, event)

        except get_cancelled_exc_class():
            raise
        except Exception as e:
            _logger.exception(e)
            raise
        finally:
            self._tg = None

    def stop(self):
        if self._tg is not None and not self._tg.cancel_scope.cancel_called:
            self._tg.cancel_scope.cancel()


_default_task_system: Optional[TaskSystem] = None


def get_task_system() -> TaskSystem:
    assert _default_task_system is not None, "TaskSystem has not been set."

    return _default_task_system


def set_task_system(task_system: TaskSystem):
    global _default_task_system

    _default_task_system = task_system
