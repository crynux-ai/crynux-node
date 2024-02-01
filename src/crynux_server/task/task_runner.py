import logging
import os.path
import shutil
import time
from abc import ABC, abstractmethod
from collections import deque
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, Deque, List, Optional, Tuple

from anyio import (
    Condition,
    CancelScope,
    Lock,
    create_task_group,
    fail_after,
    sleep_until,
    get_cancelled_exc_class,
    to_thread,
)
from celery.result import AsyncResult
from hexbytes import HexBytes
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_delay,
    wait_chain,
    wait_fixed,
)
from web3.types import EventData

from crynux_server import models
from crynux_server.config import TaskConfig as LocalConfig
from crynux_server.config import get_config
from crynux_server.contracts import Contracts, TxRevertedError, TxWaiter, get_contracts
from crynux_server.event_queue import EventQueue, get_event_queue
from crynux_server.relay import Relay, RelayError, get_relay
from crynux_server.watcher import EventWatcher, get_watcher
from crynux_worker.task.error import TaskInvalid

from .state_cache import TaskStateCache, get_task_state_cache
from .utils import make_result_commitments

_logger = logging.getLogger(__name__)


OkCallback = Callable[[bool], Awaitable[None]]
ErrCallback = Callable[[Exception], Awaitable[None]]


class TaskRunner(ABC):
    @abstractmethod
    def __init__(
        self,
        task_id: int,
        task_name: str,
        distributed: bool,
        state_cache: Optional[TaskStateCache] = None,
        queue: Optional[EventQueue] = None,
    ):
        self.task_id = task_id
        self.task_name = task_name
        self.distributed = distributed
        if state_cache is None:
            state_cache = get_task_state_cache()
        self.cache = state_cache
        if queue is None:
            queue = get_event_queue()
        self.queue = queue

        self._state: Optional[models.TaskState] = None

        self._queue_condition = Condition()
        self._deque: Deque[Tuple[int, models.TaskEvent]] = deque()

        self._state_condition = Condition()

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

    @asynccontextmanager
    async def state_context(self):
        try:
            yield
        finally:
            async with self._state_condition:
                with fail_after(10, shield=True):
                    await self.cache.dump(task_state=self.state)
                self._state_condition.notify_all()

    async def wait_for_status(self, status: models.TaskStatus):
        async with self._state_condition:
            while self.state.status != status:
                await self._state_condition.wait()

    async def init(self) -> bool:
        need_dump = False
        try:
            if self._state is None:
                if await self.cache.has(self.task_id):
                    state = await self.cache.load(self.task_id)
                    self.state = state
                else:
                    state = models.TaskState(
                        task_id=self.task_id,
                        round=0,
                        timeout=0,
                        status=models.TaskStatus.Pending,
                    )
                    self.state = state
                    need_dump = True
            # check if the task has successed or aborted
            if self.state.status in [
                models.TaskStatus.Success,
                models.TaskStatus.Aborted,
            ]:
                return False
            # check if the task exists on chain
            task = await self.get_task()
            if task is None:
                # task doesn't exist on chain, abort
                self.state.status = models.TaskStatus.Aborted
                need_dump = True
                return False
            if self.state.timeout != task.timeout:
                self.state.timeout = task.timeout
                need_dump = True
            return True
        finally:
            if self._state is not None and need_dump:
                await self.cache.dump(self.state)

    async def process_event(
        self, event: models.TaskEvent, finish_callback: Callable[[], Awaitable[None]]
    ):
        _logger.debug(f"Process event {event}")
        if event.kind == "TaskCreated":
            assert isinstance(event, models.TaskCreated)
            return await self.task_created(event, finish_callback)
        elif event.kind == "TaskResultReady":
            assert isinstance(event, models.TaskResultReady)
            return await self.result_ready(event, finish_callback)
        elif event.kind == "TaskResultCommitmentsReady":
            assert isinstance(event, models.TaskResultCommitmentsReady)
            return await self.commitment_ready(event, finish_callback)
        elif event.kind == "TaskSuccess":
            assert isinstance(event, models.TaskSuccess)
            return await self.task_success(event, finish_callback)
        if event.kind == "TaskAborted":
            assert isinstance(event, models.TaskAborted)
            return await self.task_aborted(event, finish_callback)
        else:
            raise ValueError(f"Unknown event kind {event.kind}")

    @abstractmethod
    async def task_created(
        self, event: models.TaskCreated, finish_callback: Callable[[], Awaitable[None]]
    ):
        ...

    @abstractmethod
    async def result_ready(
        self,
        event: models.TaskResultReady,
        finish_callback: Callable[[], Awaitable[None]],
    ):
        ...

    @abstractmethod
    async def commitment_ready(
        self,
        event: models.TaskResultCommitmentsReady,
        finish_callback: Callable[[], Awaitable[None]],
    ):
        ...

    @abstractmethod
    async def task_success(
        self, event: models.TaskSuccess, finish_callback: Callable[[], Awaitable[None]]
    ):
        ...

    @abstractmethod
    async def task_aborted(
        self, event: models.TaskAborted, finish_callback: Callable[[], Awaitable[None]]
    ):
        ...

    @abstractmethod
    async def cleanup(self):
        ...

    @abstractmethod
    async def get_task(self) -> Optional[models.ChainTask]:
        ...

    @abstractmethod
    async def cancel_task(self):
        ...

    async def _run_event(
        self,
        ack_id: int,
        event: models.TaskEvent,
        finish_callback: Callable[[], Awaitable[None]],
    ):
        try:
            await self.process_event(event, finish_callback)
            # sheild the ack operator from cancel to ensure the event to be acked when finish_callback is being called
            with fail_after(10, shield=True):
                await self.queue.ack(ack_id)
        except get_cancelled_exc_class():
            _logger.debug(f"Task {self.task_id} process event {event.kind} cancelled.")
            self._deque.append((ack_id, event))
            raise
        except Exception:
            _logger.debug(f"Task {self.task_id} process event {event.kind} failed.")
            self._deque.append((ack_id, event))
            raise

    async def run(self):
        try:
            success = await self.init()
            if not success:
                return
            delay = self.state.timeout - time.time()
            if delay <= 0:
                raise TimeoutError
            with fail_after(delay, shield=False):
                async with create_task_group() as tg:

                    async def finish_callback():
                        tg.cancel_scope.cancel()

                    while True:
                        ack_id, event = await self.recv()

                        tg.start_soon(self._run_event, ack_id, event, finish_callback)
        except get_cancelled_exc_class():
            raise
        except TimeoutError:
            # cancel task
            async with self.state_context():
                self.state.status = models.TaskStatus.Aborted
            await self.cancel_task()
        finally:
            with fail_after(10, shield=True):
                if self._state is not None and (
                    self.state.status == models.TaskStatus.Aborted
                    or self.state.status == models.TaskStatus.Success
                ):
                    while len(self._deque):
                        ack_id, event = self._deque.popleft()
                        await self.queue.ack(ack_id)
                        _logger.debug(f"Ack task {self.task_id} event {event.kind}")
                    await self.cleanup()
                else:
                    while len(self._deque):
                        ack_id, event = self._deque.popleft()
                        await self.queue.no_ack(ack_id)
                        _logger.debug(f"No ack task {self.task_id} event {event.kind}")

    async def recv(self) -> Tuple[int, models.TaskEvent]:
        async with self._queue_condition:
            while len(self._deque) == 0:
                await self._queue_condition.wait()
            ack_id, event = self._deque.popleft()
            return ack_id, event

    async def send(self, ack_id: int, event: models.TaskEvent):
        async with self._queue_condition:
            self._deque.append((ack_id, event))
            self._queue_condition.notify(1)


class OnceEventPusher(object):
    def __init__(self, queue: EventQueue) -> None:
        self.queue = queue

        self.used = False
        self.lock = Lock()

    async def push(self, event_data: EventData):
        async with self.lock:
            if not self.used:
                event = models.load_event_from_contracts(event_data)
                await self.queue.put(event)
                self.used = True
                _logger.debug(f"push event {event_data} to queue successfully")
            else:
                _logger.debug(f"cannot push event {event_data} to queue twice")


class InferenceTaskRunner(TaskRunner):
    def __init__(
        self,
        task_id: int,
        task_name: str,
        distributed: bool,
        state_cache: Optional[TaskStateCache] = None,
        queue: Optional[EventQueue] = None,
        contracts: Optional[Contracts] = None,
        relay: Optional[Relay] = None,
        watcher: Optional[EventWatcher] = None,
        local_config: Optional[LocalConfig] = None,
    ) -> None:
        super().__init__(
            task_id=task_id,
            task_name=task_name,
            distributed=distributed,
            state_cache=state_cache,
            queue=queue,
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

        self._cleaned = False

        self._commitment_watch_id = self.watcher.watch_event(
            "task",
            "TaskResultCommitmentsReady",
            callback=OnceEventPusher(self.queue).push,
            filter_args={"taskId": self.task_id},
        )
        _logger.debug(f"commitment watcher id {self._commitment_watch_id}")
        self._success_watch_id = self.watcher.watch_event(
            "task",
            "TaskSuccess",
            callback=OnceEventPusher(self.queue).push,
            filter_args={"taskId": self.task_id},
        )
        _logger.debug(f"success watcher id {self._success_watch_id}")
        self._aborted_watch_id = self.watcher.watch_event(
            "task",
            "TaskAborted",
            callback=OnceEventPusher(self.queue).push,
            filter_args={"taskId": self.task_id},
        )
        _logger.debug(f"abort watcher id {self._aborted_watch_id}")

    async def _call_task_contract_method(self, method: str, *args, **kwargs):
        if (
            len(self.state.waiting_tx_method) == 0
            and len(self.state.waiting_tx_hash) == 0
        ):
            if method == "submitTaskResultCommitment":
                func = self.contracts.task_contract.submit_task_result_commitment
            elif method == "discloseTaskResult":
                func = self.contracts.task_contract.disclose_task_result
            elif method == "reportResultsUploaded":
                func = self.contracts.task_contract.report_results_uploaded
            elif method == "reportTaskError":
                func = self.contracts.task_contract.report_task_error
            else:
                raise ValueError(f"Unsupported task contract method: {method}")
            waiter = await func(*args, **kwargs)
        elif (
            self.state.waiting_tx_method == method
            and len(self.state.waiting_tx_hash) > 0
        ):
            waiter = TxWaiter(
                w3=self.contracts.w3,
                method=self.state.waiting_tx_method,
                tx_hash=HexBytes(self.state.waiting_tx_hash),
            )
        else:
            raise ValueError(
                f"Error state waiting tx method: {self.state.waiting_tx_method}, "
                f"waiting tx hash: {self.state.waiting_tx_hash} in report error"
            )

        await waiter.wait()
        async with self.state_context():
            self.state.waiting_tx_hash = b""
            self.state.waiting_tx_method = ""

    async def _report_error(self):
        async with self.state_context():
            self.state.status = models.TaskStatus.Aborted

        try:
            await self._call_task_contract_method(
                "reportTaskError", task_id=self.task_id, round=self.state.round
            )
        except TxRevertedError as e:
            _logger.error(
                f"Report error of task {self.task_id} failed due to {e.reason}"
            )

    async def get_task(self):
        task = await self.contracts.task_contract.get_task(self.task_id)
        # task not exist
        if task.id == 0 or task.id != self.task_id:
            return None
        return task

    async def cancel_task(self):
        try:
            await self.contracts.task_contract.cancel_task(self.task_id)
            _logger.info(f"Task {self.task_id} timeout. Cancel the task.")
        except TxRevertedError as e:
            _logger.error(f"Cancel task {self.task_id} failed due to {e.reason}")
        except get_cancelled_exc_class():
            raise
        except Exception as e:
            _logger.debug(f"Cancel task {self.task_id} failed")

    async def task_created(
        self, event: models.TaskCreated, finish_callback: Callable[[], Awaitable[None]]
    ):
        await self.wait_for_status(models.TaskStatus.Pending)

        async with self.state_context():
            self.state.round = event.round

        def should_retry(e: BaseException) -> bool:
            if isinstance(e, RelayError) and (
                "Task not found" in e.message or "Task not ready" in e.message
            ):
                return True
            return False

        @retry(
            stop=stop_after_delay(1800),
            wait=wait_chain(*[wait_fixed(1) for _ in range(30)] + [wait_fixed(10)]),
            retry=retry_if_exception(should_retry),
            before_sleep=before_sleep_log(_logger, logging.ERROR, exc_info=True),
            reraise=True,
        )
        async def get_task():
            return await self.relay.get_task(event.task_id)

        task = await get_task()

        if self.distributed:

            def run_distributed_task():
                from crynux_server.celery_app import get_celery

                celery = get_celery()
                kwargs = {
                    "task_id": task.task_id,
                    "task_type": int(event.task_type),
                    "task_args": task.task_args,
                    "distributed": True,
                }
                res: AsyncResult = celery.send_task(
                    self.task_name,
                    kwargs=kwargs,
                )
                res.get()

            await to_thread.run_sync(run_distributed_task, cancellable=True)
            async with self.state_context():
                self.state.status = models.TaskStatus.Executing

        else:

            def run_local_task():
                import crynux_worker.task as h_task
                from crynux_worker.task.utils import get_image_hash, get_gpt_resp_hash

                assert self.local_config is not None
                proxy = None
                if self.local_config.proxy is not None:
                    proxy = self.local_config.proxy.model_dump()

                task_func = getattr(h_task, self.task_name)
                kwargs = dict(
                    task_id=task.task_id,
                    task_type=int(event.task_type),
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

                result_dir = os.path.join(
                    self.local_config.output_dir, str(task.task_id)
                )
                result_files = sorted(os.listdir(result_dir))
                result_paths = [os.path.join(result_dir, file) for file in result_files]
                if event.task_type == models.TaskType.SD:
                    hashes = [get_image_hash(path) for path in result_paths]
                else:
                    hashes = [get_gpt_resp_hash(path) for path in result_paths]
                return models.TaskResultReady(
                    task_id=self.task_id,
                    hashes=hashes,
                    files=result_paths,
                )

            try:
                next_event = await to_thread.run_sync(run_local_task, cancellable=True)
                async with self.state_context():
                    self.state.status = models.TaskStatus.Executing
                await self.queue.put(next_event)
            except TaskInvalid as e:
                _logger.exception(e)
                _logger.error("Task error, report error to the chain.")
                with fail_after(delay=60, shield=True):
                    await self._report_error()
                await finish_callback()

    async def result_ready(
        self,
        event: models.TaskResultReady,
        finish_callback: Callable[[], Awaitable[None]],
    ):
        await self.wait_for_status(models.TaskStatus.Executing)

        async with self.state_context():
            if len(self.state.result) == 0:
                result, commitment, nonce = make_result_commitments(event.hashes)
                try:
                    await self._call_task_contract_method(
                        "submitTaskResultCommitment",
                        task_id=self.task_id,
                        round=self.state.round,
                        commitment=commitment,
                        nonce=nonce,
                    )
                except TxRevertedError as e:
                    # all other nodes report error
                    if "Task is aborted" in e.reason:
                        with fail_after(60, shield=True):
                            await self._report_error()
                        await finish_callback()
                self.state.result = result
            _logger.info(f"Task {self.task_id} result 0x{self.state.result.hex()}")
            self.state.status = models.TaskStatus.ResultUploaded
            self.state.files = event.files

    async def commitment_ready(
        self,
        event: models.TaskResultCommitmentsReady,
        finish_callback: Callable[[], Awaitable[None]],
    ):
        await self.wait_for_status(models.TaskStatus.ResultUploaded)

        async with self.state_context():
            assert (
                len(self.state.result) > 0
            ), "Task result not found when receive event TaskResultCommitmentsReady."
            if not self.state.disclosed:
                await self._call_task_contract_method(
                    "discloseTaskResult",
                    task_id=self.task_id,
                    round=self.state.round,
                    result=self.state.result,
                )
                self.state.disclosed = True
            self.state.status = models.TaskStatus.Disclosed

    async def task_success(
        self, event: models.TaskSuccess, finish_callback: Callable[[], Awaitable[None]]
    ):
        await self.wait_for_status(models.TaskStatus.Disclosed)

        async with self.state_context():
            if event.result_node == self.contracts.account:
                await self.relay.upload_task_result(self.task_id, self.state.files)
                await self._call_task_contract_method(
                    "reportResultsUploaded",
                    task_id=self.task_id,
                    round=self.state.round,
                )

            self.state.status = models.TaskStatus.Success
        await finish_callback()

    async def task_aborted(
        self, event: models.TaskAborted, finish_callback: Callable[[], Awaitable[None]]
    ):
        """
        Receiving TaskAborted event means other nodes has reported error,
        so we should report error as well to avoid being slashed.
        But we can only report error before calling submitTaskResultCommitment.
        If we have called submitTaskResultCommitment, we should not finish the task runner,
        otherwise this node will be blocked on this task forever. In the contrast,
        we should make the task runner running until the task deadline and the cancel the task.
        """

        # call finish callback to finish all other event processors
        await finish_callback()
        if self.state.status in [
            models.TaskStatus.Pending,
            models.TaskStatus.Executing,
        ]:
            with fail_after(60, shield=True):
                await self._report_error()
        else:
            with CancelScope(shield=True):
                async with self.state_context():
                    self.state.status = models.TaskStatus.Aborted
                await sleep_until(self.state.timeout + 1)

    async def cleanup(self):
        if not self._cleaned:
            self.watcher.unwatch_event(self._commitment_watch_id)
            self.watcher.unwatch_event(self._success_watch_id)
            self.watcher.unwatch_event(self._aborted_watch_id)

            def delete_result_files(files: List[str]):
                if len(files) > 0:
                    dirname = os.path.dirname(files[0])
                    if os.path.exists(dirname):
                        shutil.rmtree(dirname)

            with fail_after(10, shield=True):
                await to_thread.run_sync(delete_result_files, self.state.files)

            del self.state
            self._cleaned = True


class MockTaskRunner(TaskRunner):
    def __init__(
        self,
        task_id: int,
        task_name: str,
        distributed: bool,
        state_cache: Optional[TaskStateCache] = None,
        queue: Optional[EventQueue] = None,
        timeout: int = 900,
    ):
        super().__init__(
            task_id=task_id,
            task_name=task_name,
            distributed=distributed,
            state_cache=state_cache,
            queue=queue,
        )

        self._timeout = timeout

    async def get_task(self):
        return models.ChainTask(
            id=self.task_id,
            creator="",
            task_type=models.TaskType.SD,
            task_hash=b"",
            data_hash=b"",
            vram_limit=0,
            is_success=False,
            selected_nodes=[],
            commitments=[],
            nonces=[],
            results=[],
            result_disclosed_rounds=[],
            result_node="",
            aborted=False,
            timeout=self._timeout + int(time.time()),
        )

    async def cancel_task(self):
        pass

    async def task_created(
        self, event: models.TaskCreated, finish_callback: Callable[[], Awaitable[None]]
    ):
        await self.wait_for_status(models.TaskStatus.Pending)

        async with self.state_context():
            self.state.round = event.round
            self.state.status = models.TaskStatus.Executing

    async def result_ready(
        self,
        event: models.TaskResultReady,
        finish_callback: Callable[[], Awaitable[None]],
    ):
        await self.wait_for_status(models.TaskStatus.Executing)

        async with self.state_context():
            self.state.files = event.files
            self.state.result = b"".join([bytes.fromhex(h[2:]) for h in event.hashes])
            self.state.status = models.TaskStatus.ResultUploaded

    async def commitment_ready(
        self,
        event: models.TaskResultCommitmentsReady,
        finish_callback: Callable[[], Awaitable[None]],
    ):
        await self.wait_for_status(models.TaskStatus.ResultUploaded)

        async with self.state_context():
            self.state.status = models.TaskStatus.Disclosed
            self.state.disclosed = True

    async def task_success(
        self, event: models.TaskSuccess, finish_callback: Callable[[], Awaitable[None]]
    ):
        await self.wait_for_status(models.TaskStatus.Disclosed)

        async with self.state_context():
            self.state.status = models.TaskStatus.Success
        await finish_callback()

    async def task_aborted(
        self, event: models.TaskAborted, finish_callback: Callable[[], Awaitable[None]]
    ):
        await finish_callback()
        with fail_after(10, shield=True):
            async with self.state_context():
                self.state.status = models.TaskStatus.Aborted

    async def cleanup(self):
        del self.state
