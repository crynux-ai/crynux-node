import logging
from typing import Dict, Optional, Type, TypeVar

from anyio import create_task_group, get_cancelled_exc_class, sleep
from anyio.abc import TaskGroup
from tenacity import retry, stop_after_attempt, stop_never, wait_fixed

from crynux_server.contracts import Contracts
from crynux_server.models import TaskStatus

from .state_cache import TaskStateCache
from .task_runner import InferenceTaskRunner, TaskRunner

_logger = logging.getLogger(__name__)


T = TypeVar("T", bound=TaskRunner)


def _is_task_id_commitment_empty(task_id_commitment: bytes):
    return all(v == 0 for v in task_id_commitment)


class TaskSystem(object):
    def __init__(
        self,
        state_cache: TaskStateCache,
        contracts: Contracts,
        retry: bool = True,
        task_name: str = "inference",
        interval: int = 1,
    ) -> None:
        self._state_cache = state_cache
        self._contracts = contracts
        self._retry = retry
        self._task_name = task_name
        self._interval = interval

        self._tg: Optional[TaskGroup] = None

        self._runners: Dict[bytes, TaskRunner] = {}

        self._runner_cls: Type[TaskRunner] = InferenceTaskRunner

    def set_runner_cls(self, runner_cls: Type[TaskRunner]):
        self._runner_cls = runner_cls

    @property
    def state_cache(self) -> TaskStateCache:
        return self._state_cache

    async def _run_task(self, task_id_commitment: bytes):
        try:
            runner = self._runners[task_id_commitment]

            @retry(
                stop=stop_never if self._retry else stop_after_attempt(1),
                wait=wait_fixed(30),
                reraise=True,
            )
            async def _run_task_with_retry():
                try:
                    await runner.run(self._interval)
                except get_cancelled_exc_class():
                    raise
                except Exception as e:
                    _logger.exception(e)
                    _logger.error(
                        f"Task {task_id_commitment.hex()} error: {str(e)}"
                    )
                    raise
            
            await _run_task_with_retry()

        finally:
            del self._runners[task_id_commitment]

    async def _get_node_task(self):
        return await self._contracts.task_contract.get_node_task(
            self._contracts.account
        )

    async def _recover(self, tg: TaskGroup):
        running_status = [
            TaskStatus.Queued,
            TaskStatus.Started,
            TaskStatus.ParametersUploaded,
            TaskStatus.ScoreReady,
            TaskStatus.Validated,
            TaskStatus.GroupValidated,
        ]
        running_states = await self.state_cache.find(status=running_status)
        for state in running_states:
            runner = self._runner_cls(
                task_id_commitment=state.task_id_commitment,
                task_name=self._task_name,
                state_cache=self._state_cache,
                contracts=self._contracts,
            )
            runner.state = state
            self._runners[state.task_id_commitment] = runner
            tg.start_soon(self._run_task, state.task_id_commitment)
            _logger.debug(f"Recreate task runner for {state.task_id_commitment.hex()}")

    async def start(self):
        @retry(
            stop=stop_never if self._retry else stop_after_attempt(1),
            wait=wait_fixed(30),
            reraise=True,
        )
        async def _start():
            assert self._tg is None, "The TaskSystem has already been started."

            try:
                async with create_task_group() as tg:
                    self._tg = tg
                    await self._recover(tg)
                    while True:
                        task_id_commitment = await self._get_node_task()
                        if (
                            not _is_task_id_commitment_empty(task_id_commitment)
                            and task_id_commitment not in self._runners
                        ):
                            runner = self._runner_cls(
                                task_id_commitment=task_id_commitment,
                                task_name=self._task_name,
                                state_cache=self._state_cache,
                                contracts=self._contracts,
                            )
                            self._runners[task_id_commitment] = runner
                            tg.start_soon(self._run_task, task_id_commitment)
                        
                        await sleep(self._interval)

            except get_cancelled_exc_class():
                raise
            except Exception as e:
                _logger.error(f"Some error occurs when running task system, retrying")
                _logger.exception(e)
                raise
            finally:
                self._tg = None

        await _start()

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
