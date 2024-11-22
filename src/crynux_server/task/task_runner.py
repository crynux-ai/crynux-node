import json
import logging
import os.path
import random
import shutil
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, List, Optional

from anyio import (fail_after, get_cancelled_exc_class, sleep, to_thread, move_on_after)
from hexbytes import HexBytes
from tenacity import (retry,  stop_after_attempt,
                      wait_fixed)

from crynux_server import models
from crynux_server.config import Config, get_config
from crynux_server.contracts import (Contracts, TxRevertedError, TxWaiter,
                                     get_contracts)
from crynux_server.relay import Relay, get_relay
from crynux_server.worker_manager import TaskInvalid

from .state_cache import TaskStateCache, get_task_state_cache
from .utils import run_task

_logger = logging.getLogger(__name__)


OkCallback = Callable[[bool], Awaitable[None]]
ErrCallback = Callable[[Exception], Awaitable[None]]


class TaskRunner(ABC):
    @abstractmethod
    def __init__(
        self,
        task_id_commitment: bytes,
        task_name: str,
        state_cache: Optional[TaskStateCache] = None,
        contracts: Optional[Contracts] = None
    ):
        self.task_id_commitment = task_id_commitment
        self.task_name = task_name
        if state_cache is None:
            state_cache = get_task_state_cache()
        self.cache = state_cache
        if contracts is None:
            contracts = get_contracts()
        self.contracts = contracts

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

    @asynccontextmanager
    async def state_context(self):
        try:
            yield
        finally:
            with fail_after(10, shield=True):
                await self.cache.dump(task_state=self.state)

    async def sync_status(self):
        need_dump = False
        try:
            if self._state is None:
                if await self.cache.has(self.task_id_commitment):
                    state = await self.cache.load(self.task_id_commitment)
                    self.state = state
                else:
                    state = models.TaskState(
                        task_id_commitment=self.task_id_commitment,
                        timeout=0,
                        status=models.TaskStatus.Queued,
                        task_type=models.TaskType.SD
                    )
                    self.state = state
                    need_dump = True

            task = await self.get_task()
            if self.state.timeout != task.timeout:
                self.state.timeout = task.timeout
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

    async def should_stop(self):
        return self.state.status in [
            models.TaskStatus.EndAborted,
            models.TaskStatus.EndGroupRefund,
            models.TaskStatus.EndGroupSuccess,
            models.TaskStatus.EndInvalidated,
            models.TaskStatus.EndSuccess,
            models.TaskStatus.ErrorReported
        ]

    async def change_task_status(self, status: models.TaskStatus, interval: float = 1):
        if status == self.state.status:
            await sleep(interval)
            return
        async with self.state_context():
            if status == models.TaskStatus.ParametersUploaded:
                await self.execute_task()
            elif status == models.TaskStatus.Validated or status == models.TaskStatus.GroupValidated:
                await self.upload_result()
            self.state.status = status

    async def run(self, interval: float = 1):
        try:
            await self.sync_status()
            if self.should_stop():
                return
            delay = self.state.timeout - time.time()
            if delay <= 0:
                raise TimeoutError
            with fail_after(delay, shield=False):
                while not self.should_stop():
                    task = await self.get_task()
                    await self.change_task_status(task.status, interval=interval)
        except TimeoutError:
            # cancel task
            if not self.should_stop():
                await self.cancel_task()
                async with self.state_context():
                    self.state.status = models.TaskStatus.EndAborted
        finally:
            if self.should_stop():
                with move_on_after(5, shield=True):
                    await self.cleanup()


class InferenceTaskRunner(TaskRunner):
    def __init__(
        self,
        task_id_commitment: bytes,
        task_name: str,
        state_cache: Optional[TaskStateCache] = None,
        contracts: Optional[Contracts] = None,
        relay: Optional[Relay] = None,
        config: Optional[Config] = None,
    ) -> None:
        super().__init__(
            task_id_commitment=task_id_commitment,
            task_name=task_name,
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
            self.state.status = models.TaskStatus.ErrorReported

        try:
            await self._call_task_contract_method(
                "reportTaskError", task_id_commitment=self.task_id_commitment, error=models.TaskError.ParametersValidationFailed
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
            raise ValueError("Task not found")
        return task

    async def cancel_task(self):
        try:
            waiter = await self.contracts.task_contract.abort_task(self.task_id_commitment, models.TaskAbortReason.Timeout)
            await waiter.wait()
            _logger.info(f"Task {self.task_id_commitment.hex()} timeout. Cancel the task.")
        except TxRevertedError as e:
            if "Task not exist" not in e.reason:
                _logger.error(f"Cancel task {self.task_id_commitment.hex()} failed due to {e.reason}")
                raise
        except get_cancelled_exc_class():
            raise
        except Exception as e:
            _logger.debug(f"Cancel task {self.task_id_commitment.hex()} failed")
            raise

    async def execute_task(self):
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_fixed(30),
            reraise=True,
        )
        async def get_task():
            return await self.relay.get_task(self.task_id_commitment)
        
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_fixed(30),
            reraise=True,
        )
        async def get_checkpoint(checkpoint_dir: str):
            await self.relay.get_checkpoint(self.task_id_commitment, checkpoint_dir)

        async def execute_task_in_worker():
            task_dir = os.path.join(self.config.task_config.output_dir, self.task_id_commitment.hex())
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
            _logger.info("Start executing task")
            if not os.path.exists(task_dir):
                os.makedirs(task_dir, exist_ok=True)
            try:
                files, hashes, checkpoint = await run_task(
                    task_name=self.task_name,
                    task_id_commitment=self.task_id_commitment,
                    task_type=self.state.task_type,
                    task_args=task.task_args,
                    task_dir=task_dir,
                )
                _logger.info("Task execution success")
                async with self.state_context():
                    self.state.files = files
                    self.state.score = b"".join(hashes)
                    self.state.checkpoint = checkpoint
            except TaskInvalid as e:
                _logger.exception(e)
                _logger.error("Task error, report error to the chain.")
                with fail_after(delay=60, shield=True):
                    await self._report_error()

        if len(self.state.files) == 0 or len(self.state.score) == 0 or len(self.state.checkpoint) == 0:
            await execute_task_in_worker()

        await self._call_task_contract_method("submitTaskScore", task_id_commitment=self.task_id_commitment, score=self.state.score)
        _logger.info("Submiting task score success")

    async def upload_result(self):
        async with self.state_context():
            await self.relay.upload_task_result(self.task_id_commitment, self.state.files, self.state.checkpoint)
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


class MockTaskRunner(TaskRunner):
    def __init__(
        self,
        task_id_commitment: bytes,
        task_name: str,
        state_cache: Optional[TaskStateCache] = None,
        contracts: Optional[Contracts] = None,
        timeout: int = 900,
    ):
        super().__init__(
            task_id_commitment=task_id_commitment,
            task_name=task_name,
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
            status=models.TaskStatus.Queued,
            selected_node="",
            timeout=int(time.time()) + self._timeout,
            score=b"",
            task_fee=0,
            task_size=1,
            model_id="crynux-ai/stable-diffusion-v1-5",
            min_vram=0,
            required_gpu="",
            required_gpu_vram=0,
            task_version="2.0.0",
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
