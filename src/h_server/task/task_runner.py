import logging
import os.path
import shutil
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import List, Optional

from anyio import Lock, fail_after, to_thread
from celery.result import AsyncResult
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry,
    retry_if_exception,
    retry_if_not_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_fixed,
)
from web3.types import EventData

from h_server import models
from h_server.config import TaskConfig as LocalConfig
from h_server.config import get_config
from h_server.contracts import Contracts, TxRevertedError, get_contracts
from h_server.event_queue import EventQueue
from h_server.relay import Relay, get_relay, RelayError
from h_server.watcher import EventWatcher, get_watcher
from h_worker.task.error import TaskInvalid

from .state_cache import TaskStateCache
from .utils import make_result_commitments

_logger = logging.getLogger(__name__)


class TaskRunner(ABC):
    @abstractmethod
    def __init__(
        self,
        task_id: int,
        state_cache: TaskStateCache,
        queue: EventQueue,
        task_name: str,
        distributed: bool,
    ):
        self.task_id = task_id
        self.cache = state_cache
        self.queue = queue
        self.task_name = task_name
        self.distributed = distributed

        self._state: Optional[models.TaskState] = None

    @property
    def state(self) -> models.TaskState:
        assert self._state is not None, "The task runner's state has not been set."
        return self._state

    @state.setter
    def state(self, state: models.TaskState):
        assert self._state is None, "The task runner's state has already been set."
        self._state = state

    @state.deleter
    def state(self):
        assert self._state is not None, "The task runner's state has not been set."
        self._state = None

    async def init(self) -> bool:
        try:
            if await self.cache.has(self.task_id):
                state = await self.cache.load(self.task_id)
                self.state = state
            else:
                state = models.TaskState(
                    task_id=self.task_id,
                    round=0,
                    status=models.TaskStatus.Pending,
                )
                await self.cache.dump(state)
                self.state = state
            return True
        except KeyError:
            return False

    @abstractmethod
    async def process_event(self, event: models.TaskEvent) -> bool:
        ...


class InferenceTaskRunner(TaskRunner):
    def __init__(
        self,
        task_id: int,
        state_cache: TaskStateCache,
        queue: EventQueue,
        task_name: str,
        distributed: bool,
        contracts: Optional[Contracts] = None,
        relay: Optional[Relay] = None,
        watcher: Optional[EventWatcher] = None,
        local_config: Optional[LocalConfig] = None,
        retry_count: int = 5,
    ) -> None:
        super().__init__(
            task_id=task_id,
            state_cache=state_cache,
            queue=queue,
            task_name=task_name,
            distributed=distributed,
        )
        if contracts is None:
            self.contracts = get_contracts()
        else:
            self.contracts = contracts
        if relay is None:
            self.relay = get_relay()
        else:
            self.relay = relay
        if watcher is None:
            self.watcher = get_watcher()
        else:
            self.watcher = watcher

        if not self.distributed:
            # load task local config only in non-distributed mode
            if local_config is None:
                config = get_config()
                assert (
                    config.task_config is not None
                ), "Default task local config not found in config."
                self.local_config = config.task_config
            else:
                self.local_config = local_config
        else:
            self.local_config = None

        self._retry_count = retry_count

        self._lock: Optional[Lock] = None

        async def _push_event(event_data: EventData):
            event = models.load_event_from_contracts(event_data)
            await self.queue.put(event)

        self._commitment_watch_id = self.watcher.watch_event(
            "task",
            "TaskResultCommitmentsReady",
            callback=_push_event,
            filter_args={"taskId": self.task_id},
        )
        self._success_watch_id = self.watcher.watch_event(
            "task",
            "TaskSuccess",
            callback=_push_event,
            filter_args={"taskId": self.task_id},
        )
        self._aborted_watch_id = self.watcher.watch_event(
            "task",
            "TaskAborted",
            callback=_push_event,
            filter_args={"taskId": self.task_id},
        )

    @asynccontextmanager
    async def state_context(self):
        try:
            yield self.state
        finally:
            with fail_after(5, shield=True):
                await self.cache.dump(task_state=self.state)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(10),
        retry=retry_if_not_exception_type(TxRevertedError),
        before_sleep=before_sleep_log(_logger, logging.ERROR, exc_info=True),
        reraise=True,
    )
    async def _report_error(self):
        async with self.state_context() as state:
            round = state.round
            state.status = models.TaskStatus.Error

        waiter = await self.contracts.task_contract.report_task_error(
            self.task_id, round
        )
        await waiter.wait()
        await self.cleanup()

    @property
    def lock(self) -> Lock:
        if self._lock is None:
            self._lock = Lock()
        return self._lock

    async def process_event(self, event: models.TaskEvent):
        try:
            async with self.lock:
                async for attemp in AsyncRetrying(
                    stop=stop_after_attempt(self._retry_count),
                    wait=wait_exponential(multiplier=10),
                    retry=retry_if_not_exception_type((TaskInvalid, AssertionError)),
                    before_sleep=before_sleep_log(
                        _logger, logging.ERROR, exc_info=True
                    ),
                    reraise=True,
                ):
                    with attemp:
                        _logger.debug(f"Process event {event}")
                        if event.kind == "TaskCreated":
                            assert isinstance(event, models.TaskCreated)
                            await self.task_created(event)
                            return False
                        elif event.kind == "TaskResultReady":
                            assert isinstance(event, models.TaskResultReady)
                            await self.result_ready(event)
                            return False
                        elif event.kind == "TaskResultCommitmentsReady":
                            assert isinstance(event, models.TaskResultCommitmentsReady)
                            await self.commitment_ready(event)
                            return False
                        elif event.kind == "TaskSuccess":
                            assert isinstance(event, models.TaskSuccess)
                            await self.task_success(event)
                            return True
                        elif event.kind == "TaskAborted":
                            assert isinstance(event, models.TaskAborted)
                            await self.task_aborted(event)
                            return True
                        else:
                            raise ValueError(f"Unknown event kind {event.kind}")
        except TaskInvalid as e:
            _logger.exception(e)
            _logger.error("Task error, report error to the chain.")
            with fail_after(delay=60, shield=True):
                await self._report_error()
            return True

    async def task_created(self, event: models.TaskCreated):
        async with self.state_context() as state:
            assert (
                state.status == models.TaskStatus.Pending
            ), "Task status is not pending when receive event TaskCreated."

            state.round = event.round

            def should_retry(e: BaseException) -> bool:
                if isinstance(e, RelayError) and (
                    "Task not found" in e.message or "Task not ready" in e.message
                ):
                    return True
                return False

            @retry(
                stop=stop_after_delay(1800),
                wait=wait_fixed(60),
                retry=retry_if_exception(should_retry),
                before_sleep=before_sleep_log(_logger, logging.ERROR, exc_info=True),
                reraise=True,
            )
            async def get_task():
                return await self.relay.get_task(event.task_id)

            task = await get_task()

            if self.distributed:

                def run_distributed_task():
                    from h_server.celery_app import get_celery

                    celery = get_celery()
                    kwargs = {
                        "task_id": task.task_id,
                        "task_args": task.task_args,
                        "distributed": True,
                    }
                    res: AsyncResult = celery.send_task(
                        self.task_name,
                        kwargs=kwargs,
                    )
                    res.get()

                await to_thread.run_sync(run_distributed_task, cancellable=True)
                state.status = models.TaskStatus.Executing

            else:

                def run_local_task():
                    import h_worker.task as h_task
                    from h_worker.task.utils import get_image_hash

                    assert self.local_config is not None
                    proxy = None
                    if self.local_config.proxy is not None:
                        proxy = self.local_config.proxy.model_dump()

                    task_func = getattr(h_task, self.task_name)
                    kwargs = dict(
                        task_id=task.task_id,
                        task_args=task.task_args,
                        distributed=False,
                        result_url="",
                        output_dir=self.local_config.output_dir,
                        hf_cache_dir=self.local_config.hf_cache_dir,
                        external_cache_dir=self.local_config.external_cache_dir,
                        script_dir=self.local_config.script_dir,
                        inference_logs_dir=self.local_config.inference_logs_dir,
                        proxy=proxy,
                    )

                    task_func(**kwargs)

                    image_dir = os.path.join(
                        self.local_config.output_dir, str(task.task_id)
                    )
                    image_files = sorted(os.listdir(image_dir))
                    image_paths = [
                        os.path.join(image_dir, file) for file in image_files
                    ]
                    hashes = [get_image_hash(path) for path in image_paths]
                    return models.TaskResultReady(
                        task_id=self.task_id,
                        hashes=hashes,
                        files=image_paths,
                    )

                next_event = await to_thread.run_sync(run_local_task, cancellable=True)
                state.status = models.TaskStatus.Executing
                await self.result_ready(next_event)

    async def result_ready(self, event: models.TaskResultReady):
        async with self.state_context() as state:
            assert (
                state.status == models.TaskStatus.Executing
            ), "Task status is not executing when receive event TaskResultReady."

            if len(state.result) == 0:
                result, commitment, nonce = make_result_commitments(event.hashes)
                try:
                    waiter = (
                        await self.contracts.task_contract.submit_task_result_commitment(
                            task_id=self.task_id,
                            round=state.round,
                            commitment=commitment,
                            nonce=nonce,
                        )
                    )
                    await waiter.wait()
                except TxRevertedError as e:
                    # all other nodes report error
                    if "Task is aborted" in e.reason:
                        await self._report_error()
                        return
                state.result = result
            _logger.info(f"Task {self.task_id} result 0x{state.result.hex()}")
            state.status = models.TaskStatus.ResultUploaded
            state.files = event.files

    async def commitment_ready(self, event: models.TaskResultCommitmentsReady):
        async with self.state_context() as state:
            assert (
                state.status == models.TaskStatus.ResultUploaded
            ), "Task status is not result_uploaded when receive event TaskResultCommitmentsReady."
            assert (
                len(state.result) > 0
            ), "Task result not found when receive event TaskResultCommitmentsReady."
            if not state.disclosed:
                waiter = await self.contracts.task_contract.disclose_task_result(
                    task_id=self.task_id,
                    round=state.round,
                    result=state.result,
                )
                await waiter.wait()
                state.disclosed = True
            state.status = models.TaskStatus.Disclosed

    async def task_success(self, event: models.TaskSuccess):
        async with self.state_context() as state:
            assert (
                state.status == models.TaskStatus.Disclosed
            ), "Task status is not disclosed when receive event TaskSuccess."

            if event.result_node == self.contracts.account:
                await self.relay.upload_task_result(self.task_id, state.files)
                waiter = await self.contracts.task_contract.report_results_uploaded(
                    self.task_id, state.round
                )
                await waiter.wait()

            state.status = models.TaskStatus.Success

        await self.cleanup()

    async def task_aborted(self, event: models.TaskAborted):
        async with self.state_context() as state:
            state.status = models.TaskStatus.Aborted

        await self.cleanup()

    async def cleanup(self):
        assert self.state.status in [
            models.TaskStatus.Success,
            models.TaskStatus.Aborted,
            models.TaskStatus.Error,
        ], "Task status is not success or aborted when shutdown."

        self.watcher.unwatch_event(self._commitment_watch_id)
        self.watcher.unwatch_event(self._success_watch_id)
        self.watcher.unwatch_event(self._aborted_watch_id)

        def delete_result_files(files: List[str]):
            assert len(files) > 0
            dirname = os.path.dirname(files[0])
            if os.path.exists(dirname):
                shutil.rmtree(dirname)

        with fail_after(5, shield=True):
            await to_thread.run_sync(delete_result_files, self.state.files)

        del self.state


class MockTaskRunner(TaskRunner):
    def __init__(
        self,
        task_id: int,
        state_cache: TaskStateCache,
        queue: EventQueue,
        task_name: str,
        distributed: bool,
    ):
        super().__init__(
            task_id=task_id,
            state_cache=state_cache,
            queue=queue,
            task_name=task_name,
            distributed=distributed,
        )

        self._lock: Optional[Lock] = None

    @asynccontextmanager
    async def state_context(self):
        try:
            yield self.state
        finally:
            with fail_after(5, shield=True):
                await self.cache.dump(task_state=self.state)

    @property
    def lock(self) -> Lock:
        if self._lock is None:
            self._lock = Lock()
        return self._lock

    async def process_event(self, event: models.TaskEvent):
        async with self.lock:
            if event.kind == "TaskCreated":
                assert isinstance(event, models.TaskCreated)
                await self.task_created(event)
                return False
            elif event.kind == "TaskResultReady":
                assert isinstance(event, models.TaskResultReady)
                await self.result_ready(event)
                return False
            elif event.kind == "TaskResultCommitmentsReady":
                assert isinstance(event, models.TaskResultCommitmentsReady)
                await self.commitment_ready(event)
                return False
            elif event.kind == "TaskAborted":
                assert isinstance(event, models.TaskAborted)
                await self.task_aborted(event)
                return True
            elif event.kind == "TaskSuccess":
                assert isinstance(event, models.TaskSuccess)
                await self.task_success(event)
                return True
            else:
                raise ValueError(f"Unknown event kind {event.kind}")

    async def task_created(self, event: models.TaskCreated):
        async with self.state_context() as state:
            assert state.status == models.TaskStatus.Pending

            state.round = event.round
            state.status = models.TaskStatus.Executing

    async def result_ready(self, event: models.TaskResultReady):
        async with self.state_context() as state:
            assert state.status == models.TaskStatus.Executing

            state.files = event.files
            state.result = b"".join([bytes.fromhex(h[2:]) for h in event.hashes])
            state.status = models.TaskStatus.ResultUploaded

    async def commitment_ready(self, event: models.TaskResultCommitmentsReady):
        async with self.state_context() as state:
            assert state.status == models.TaskStatus.ResultUploaded

            state.status = models.TaskStatus.Disclosed
            state.disclosed = True

    async def task_success(self, event: models.TaskSuccess):
        async with self.state_context() as state:
            assert state.status == models.TaskStatus.Disclosed

            state.status = models.TaskStatus.Success

        await self.cleanup()

    async def task_aborted(self, event: models.TaskAborted):
        async with self.state_context() as state:
            state.status = models.TaskStatus.Aborted

        await self.cleanup()

    async def cleanup(self):
        del self.state
