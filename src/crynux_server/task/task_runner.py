import json
import logging
import os.path
import random
import re
import shutil
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, List, Optional

from anyio import (create_memory_object_stream, create_task_group, fail_after,
                   get_cancelled_exc_class, move_on_after, sleep, to_thread)
from anyio.streams.memory import (MemoryObjectReceiveStream,
                                  MemoryObjectSendStream)
from hexbytes import HexBytes
from tenacity import (retry, retry_if_exception, stop_after_delay, wait_chain,
                      wait_fixed)

from crynux_server import models
from crynux_server.config import Config, get_config
from crynux_server.contracts import (Contracts, TxRevertedError, TxWaiter,
                                     get_contracts)
from crynux_server.download_model_cache import (DownloadModelCache,
                                                get_download_model_cache)
from crynux_server.relay import Relay, get_relay
from crynux_server.worker_manager import TaskInvalid

from .state_cache import (DownloadTaskStateCache, InferenceTaskStateCache,
                          get_download_task_state_cache,
                          get_inference_task_state_cache)
from .utils import run_download_task, run_inference_task

_logger = logging.getLogger(__name__)


OkCallback = Callable[[bool], Awaitable[None]]
ErrCallback = Callable[[Exception], Awaitable[None]]


class InferenceTaskRunnerBase(ABC):
    @abstractmethod
    def __init__(
        self,
        task_id_commitment: bytes,
        state_cache: Optional[InferenceTaskStateCache] = None,
        contracts: Optional[Contracts] = None,
    ):
        self.task_id_commitment = HexBytes(task_id_commitment)
        if state_cache is None:
            state_cache = get_inference_task_state_cache()
        self.cache = state_cache
        if contracts is None:
            contracts = get_contracts()
        self.contracts = contracts

        self._state: Optional[models.InferenceTaskState] = None

    @property
    def state(self) -> models.InferenceTaskState:
        assert self._state is not None, "The task runner's state has not been set."
        return self._state

    @state.setter
    def state(self, state: models.InferenceTaskState):
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
            with fail_after(10, shield=True):
                await self.cache.dump(task_state=self.state)

    async def sync_state(self):
        need_dump = False
        try:
            if self._state is None:
                if await self.cache.has(self.task_id_commitment):
                    state = await self.cache.load(self.task_id_commitment)
                    self.state = state
                else:
                    state = models.InferenceTaskState(
                        task_id_commitment=self.task_id_commitment,
                        timeout=0,
                        status=models.InferenceTaskStatus.Queued,
                        task_type=models.TaskType.SD,
                    )
                    self.state = state
                    need_dump = True

            task = await self.get_task()
            start_timestamp = task.start_timestamp
            if start_timestamp == 0:
                start_timestamp = int(time.time())
            timeout = start_timestamp + task.timeout
            if self.state.timeout != timeout:
                self.state.timeout = timeout
                need_dump = True
            if self.state.status != task.status:
                self.state.status = task.status
                need_dump = True
            if self.state.task_type != task.task_type:
                self.state.task_type = task.task_type
                need_dump = True
        finally:
            if self._state is not None and need_dump:
                await self.cache.dump(self.state)

    @abstractmethod
    async def cleanup(self): ...

    @abstractmethod
    async def get_task(self) -> models.ChainTask: ...

    @abstractmethod
    async def cancel_task(self): ...

    @abstractmethod
    async def execute_task(self): ...

    @abstractmethod
    async def upload_result(self): ...

    def should_stop(self):
        return self.state.status in [
            models.InferenceTaskStatus.EndAborted,
            models.InferenceTaskStatus.EndGroupRefund,
            models.InferenceTaskStatus.EndGroupSuccess,
            models.InferenceTaskStatus.EndInvalidated,
            models.InferenceTaskStatus.EndSuccess,
            models.InferenceTaskStatus.ErrorReported,
        ]

    async def task_status_consumer(
        self, status_receiver: MemoryObjectReceiveStream[models.InferenceTaskStatus]
    ):
        async with status_receiver:
            async for status in status_receiver:
                _logger.info(
                    f"task {self.task_id_commitment.hex()} status: {status.name}"
                )
                if (
                    status == models.InferenceTaskStatus.Started
                    or status == models.InferenceTaskStatus.ParametersUploaded
                ):
                    await self.execute_task()
                elif (
                    status == models.InferenceTaskStatus.Validated
                    or status == models.InferenceTaskStatus.GroupValidated
                ):
                    await self.upload_result()

    async def task_status_producer(
        self,
        status_sender: MemoryObjectSendStream[models.InferenceTaskStatus],
        interval: float,
    ):
        async with status_sender:
            await status_sender.send(self.state.status)
            while not self.should_stop():
                last_status = self.state.status
                await self.sync_state()
                if last_status != self.state.status:
                    await status_sender.send(self.state.status)
                await sleep(interval)

    async def run(self, interval: float = 1):
        try:
            await self.sync_state()
            if self.should_stop():
                return
            delay = self.state.timeout - time.time()
            if delay <= 0:
                raise TimeoutError

            status_sender, status_receiver = create_memory_object_stream(
                10, item_type=models.InferenceTaskStatus
            )
            with fail_after(delay, shield=False):
                async with create_task_group() as tg:
                    tg.start_soon(self.task_status_consumer, status_receiver)
                    tg.start_soon(self.task_status_producer, status_sender, interval)
        except TimeoutError:
            # cancel task
            if not self.should_stop():
                await self.cancel_task()
                async with self.state_context():
                    self.state.status = models.InferenceTaskStatus.EndAborted
        finally:
            if self.should_stop():
                with move_on_after(5, shield=True):
                    await self.cleanup()


class InferenceTaskRunner(InferenceTaskRunnerBase):
    def __init__(
        self,
        task_id_commitment: bytes,
        state_cache: Optional[InferenceTaskStateCache] = None,
        contracts: Optional[Contracts] = None,
        relay: Optional[Relay] = None,
        config: Optional[Config] = None,
    ) -> None:
        super().__init__(
            task_id_commitment=task_id_commitment,
            state_cache=state_cache,
            contracts=contracts,
        )
        if relay is None:
            self.relay = get_relay()
        else:
            self.relay = relay
        if config is None:
            config = get_config()
        self.config = config

        self._cleaned = False

    async def _call_task_contract_method(self, method: str, *args, **kwargs):
        if (
            len(self.state.waiting_tx_method) == 0
            and len(self.state.waiting_tx_hash) == 0
        ):
            if method == "reportTaskError":
                func = self.contracts.task_contract.report_task_error
            elif method == "submitTaskScore":
                func = self.contracts.task_contract.submit_task_score
            elif method == "abortTask":
                func = self.contracts.task_contract.abort_task
            else:
                raise ValueError(f"Unsupported task contract method: {method}")
            waiter = await func(*args, **kwargs)
        elif (
            self.state.waiting_tx_method == method
            and len(self.state.waiting_tx_hash) > 0
        ):
            waiter = TxWaiter(
                w3_pool=self.contracts._w3_pool,
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
            self.state.status = models.InferenceTaskStatus.ErrorReported

        try:
            await self._call_task_contract_method(
                "reportTaskError",
                task_id_commitment=self.task_id_commitment,
                error=models.TaskError.ParametersValidationFailed,
            )
            _logger.info(
                f"Task {self.task_id_commitment.hex()} error. Report the task error to contract."
            )
        except TxRevertedError as e:
            _logger.error(
                f"Report error of task {self.task_id_commitment.hex()} failed due to {e.reason}"
            )

    async def get_task(self):
        task = await self.contracts.task_contract.get_task(self.task_id_commitment)
        # task not exist
        if task.task_id_commitment != self.task_id_commitment:
            _logger.error(
                f"local task id commitment: {self.task_id_commitment.hex()}, remote task id commitment: {task.task_id_commitment.hex()}"
            )
            raise ValueError("Task not found")
        return task

    async def cancel_task(self):
        try:
            waiter = await self.contracts.task_contract.abort_task(
                self.task_id_commitment, models.TaskAbortReason.Timeout
            )
            await waiter.wait()
            _logger.info(
                f"Task {self.task_id_commitment.hex()} timeout. Cancel the task."
            )
        except TxRevertedError as e:
            if "Task not found" not in e.reason and "Illegal node status" in e.reason:
                _logger.error(
                    f"Cancel task {self.task_id_commitment.hex()} failed due to {e.reason}"
                )
                raise
        except get_cancelled_exc_class():
            raise
        except Exception as e:
            _logger.debug(f"Cancel task {self.task_id_commitment.hex()} failed")
            raise

    async def execute_task(self):
        @retry(
            stop=stop_after_delay(180),
            wait=wait_chain(*[wait_fixed(1) for _ in range(10)] + [wait_fixed(5)]),
            reraise=True,
        )
        async def get_task():
            task = await self.relay.get_task(self.task_id_commitment)
            _logger.debug(f"get task {self.task_id_commitment.hex()} from relay")
            return task

        @retry(
            stop=stop_after_delay(180),
            wait=wait_chain(*[wait_fixed(1) for _ in range(10)] + [wait_fixed(5)]),
            reraise=True,
        )
        async def get_checkpoint(checkpoint_dir: str):
            await self.relay.get_checkpoint(self.task_id_commitment, checkpoint_dir)
            _logger.debug(f"get task {self.task_id_commitment.hex()} from relay")

        async def execute_task_in_worker():
            task_dir = os.path.join(
                self.config.task_config.output_dir, self.task_id_commitment.hex()
            )
            task = await get_task()

            if self.state.task_type == models.TaskType.SD_FT_LORA:
                args = json.loads(task.task_args)
                checkpoint = args.get("checkpoint", None)
                if checkpoint is not None:
                    checkpoint_dir = os.path.join(task_dir, "input_checkpoint")
                    await get_checkpoint(checkpoint_dir)
                    args["checkpoint"] = checkpoint_dir
                    task.task_args = json.dumps(args)

            _logger.info(
                f"task id: {self.task_id_commitment.hex()},"
                f"task type: {self.state.task_type.name},"
                f"task_args: {task.task_args},"
            )
            _logger.info(f"Start executing task {self.task_id_commitment.hex()}")
            if not os.path.exists(task_dir):
                os.makedirs(task_dir, exist_ok=True)
            try:
                task_models = [
                    models.ModelConfig.from_model_id(model_id)
                    for model_id in task.model_ids
                ]

                files, hashes, checkpoint = await run_inference_task(
                    task_id_commitment=self.task_id_commitment,
                    task_type=self.state.task_type,
                    models=task_models,
                    task_args=task.task_args,
                    task_dir=task_dir,
                )
                _logger.info(f"Task {self.task_id_commitment.hex()} execution success")
                async with self.state_context():
                    self.state.files = files
                    self.state.score = b"".join(hashes)
                    self.state.checkpoint = checkpoint
            except TaskInvalid as e:
                _logger.exception(e)
                _logger.error(
                    f"Task {self.task_id_commitment.hex()} error, report error to the chain."
                )
                with fail_after(delay=60, shield=True):
                    await self._report_error()

        def _illegal_task_state(exc: BaseException):
            return re.search(r"Illegal previous task state", str(exc)) is not None

        @retry(
            stop=stop_after_delay(180),
            wait=wait_chain(*[wait_fixed(1) for _ in range(10)] + [wait_fixed(5)]),
            retry=retry_if_exception(_illegal_task_state),
            reraise=True,
        )
        async def submit_task_score():
            await self._call_task_contract_method(
                "submitTaskScore",
                task_id_commitment=self.task_id_commitment,
                score=self.state.score,
            )
            _logger.info("Submiting task score success")

        _logger.debug(f"task {self.task_id_commitment} state: {self.state}")

        if len(self.state.files) == 0:
            await execute_task_in_worker()

        await submit_task_score()

    async def upload_result(self):
        _logger.info(f"Task {self.task_id_commitment.hex()} start uploading results")
        await self.relay.upload_task_result(
            self.task_id_commitment, self.state.files, self.state.checkpoint
        )
        _logger.info(f"Task {self.task_id_commitment.hex()} success")

    async def cleanup(self):
        if not self._cleaned:

            def delete_result_files(files: List[str]) -> None:
                if len(files) > 0:
                    dirname = os.path.dirname(files[0])
                    if os.path.exists(dirname):
                        shutil.rmtree(dirname)

            with fail_after(10, shield=True):
                await to_thread.run_sync(delete_result_files, self.state.files)

            del self.state
            self._cleaned = True


class MockInferenceTaskRunner(InferenceTaskRunnerBase):
    def __init__(
        self,
        task_id_commitment: bytes,
        state_cache: Optional[InferenceTaskStateCache] = None,
        contracts: Optional[Contracts] = None,
        timeout: int = 900,
    ):
        super().__init__(
            task_id_commitment=task_id_commitment,
            state_cache=state_cache,
            contracts=contracts,
        )

        self._timeout = timeout

    async def get_task(self):
        return models.ChainTask(
            task_type=models.TaskType.SD,
            creator="",
            task_id_commitment=random.randbytes(4),
            sampling_seed=random.randbytes(4),
            nonce=random.randbytes(4),
            sequence=random.randint(1, 10000),
            status=models.InferenceTaskStatus.Queued,
            selected_node="",
            timeout=int(time.time()) + self._timeout,
            score=b"",
            task_fee=0,
            task_size=1,
            task_model_ids=["crynux-ai/stable-diffusion-v1-5:"],
            min_vram=0,
            required_gpu="",
            required_gpu_vram=0,
            task_version=[2, 0, 0],
            abort_reason=models.TaskAbortReason.IncorrectResult,
            error=models.TaskError.ParametersValidationFailed,
            payment_addresses=[],
            payments=[],
            create_timestamp=0,
            start_timestamp=0,
            score_ready_timestamp=0,
        )

    async def cancel_task(self):
        pass

    async def execute_task(self):
        async with self.state_context():
            self.state.files = [""]
            self.state.score = random.randbytes(4)

    async def upload_result(self):
        pass

    async def cleanup(self):
        del self.state


class DownloadTaskRunner(object):
    def __init__(
        self,
        task_id: str,
        state: models.DownloadTaskState,
        state_cache: Optional[DownloadTaskStateCache] = None,
        contracts: Optional[Contracts] = None,
        download_model_cache: Optional[DownloadModelCache] = None,
    ):
        self.task_id = task_id
        if state_cache is None:
            state_cache = get_download_task_state_cache()
        self.state_cache = state_cache
        if contracts is None:
            contracts = get_contracts()
        self.contracts = contracts
        if download_model_cache is None:
            download_model_cache = get_download_model_cache()
        self.download_model_cache = download_model_cache

        self._state: models.DownloadTaskState = state

    @asynccontextmanager
    async def state_context(self):
        try:
            yield
        finally:
            with fail_after(10, shield=True):
                await self.state_cache.dump(task_state=self._state)

    async def run(self):
        if await self.state_cache.has(self.task_id):
            self._state = await self.state_cache.load(self.task_id)
        else:
            await self.state_cache.dump(self._state)

        if self._state.status == models.DownloadTaskStatus.Success:
            return

        model = models.ModelConfig.from_model_id(self._state.model_id)
        if self._state.status == models.DownloadTaskStatus.Started:
            _logger.info(f"start downloading model {self._state.model_id}")
            await run_download_task(
                task_id=self.task_id, task_type=self._state.task_type, model=model
            )
            async with self.state_context():
                self._state.status = models.DownloadTaskStatus.Executed
            _logger.info(f"Download model {self._state.model_id} successfully")

        if self._state.status == models.DownloadTaskStatus.Executed:
            waiter = await self.contracts.node_contract.report_model_downloaded(
                self._state.model_id
            )
            await waiter.wait()
            _logger.info(f"report model {self._state.model_id} is downloaded")
            async with self.state_context():
                self._state.status = models.DownloadTaskStatus.Success

            await self.download_model_cache.save(
                models.DownloadModel(task_type=self._state.task_type, model=model)
            )
