import logging
import os.path
import shutil
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, contextmanager
from typing import List, Optional

import celery.exceptions as celery_exceptions
from anyio import Lock, fail_after, get_cancelled_exc_class, to_thread
from celery.result import AsyncResult

from h_server import models
from h_server.config import TaskConfig as LocalConfig, get_config
from h_server.event_queue import EventQueue
from h_server.contracts import Contracts, TxRevertedError, get_contracts
from h_server.relay import Relay, RelayError, get_relay
from h_server.watcher import EventWatcher, get_watcher

from .exceptions import TaskError, TaskErrorSource, TaskFailure
from .state_cache import TaskStateCache
from .utils import make_result_commitments
from web3.types import EventData

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

    @abstractmethod
    async def init(self):
        ...

    @abstractmethod
    async def process_event(self, event: models.TaskEvent) -> bool:
        ...


@contextmanager
def wrap_task_error():
    try:
        yield
    except get_cancelled_exc_class() as e:
        raise e
    except AssertionError as e:
        _logger.exception(e)
        _logger.error("Task assert error")
        raise TaskError(str(e), TaskErrorSource.Unknown, retry=False)
    except RelayError as e:
        retry = e.status_code == 400 and (
            "Task not found" in e.message or "Task not ready" in e.message
        )
        if not retry:
            _logger.exception(e)
            _logger.error("Task relay error")
        else:
            _logger.error("Retry for task relay error")
        raise TaskError(str(e), TaskErrorSource.Relay, retry=retry)
    except TxRevertedError as e:
        _logger.exception(e)
        _logger.error("Task contracts error")
        raise TaskError(str(e), TaskErrorSource.Contracts, retry=False)
    except celery_exceptions.CeleryError as e:
        retry = isinstance(e, celery_exceptions.TimeoutError) or isinstance(
            e, celery_exceptions.Retry
        )
        if not retry:
            _logger.exception(e)
            _logger.error("Task celery error")
        else:
            _logger.error("Retry for celery error")
        raise TaskError(str(e), TaskErrorSource.Celery, retry=retry)
    except TaskFailure as e:
        _logger.error("Task celery execution failed")
        raise TaskError(str(e), TaskErrorSource.Celery, retry=True)
    except Exception as e:
        _logger.exception(e)
        _logger.error("Task unknown error")
        raise TaskError(str(e), TaskErrorSource.Unknown, retry=False)


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

        self._state: Optional[models.TaskState] = None

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

    async def init(self):
        assert self._state is None, "The task runner has already been initialized."

        if await self.cache.has(self.task_id):
            state = await self.cache.load(self.task_id)
            self._state = state
        else:
            self._state = models.TaskState(
                task_id=self.task_id,
                round=0,
                status=models.TaskStatus.Pending,
            )

    @asynccontextmanager
    async def state_context(self):
        try:
            yield
        finally:
            if self._state is not None:
                with fail_after(5, shield=True):
                    await self.cache.dump(task_state=self._state)

    async def _report_error(self):
        assert self._state is not None, "The task runner has not been initialized."

        round = self._state.round

        await self.contracts.task_contract.report_task_error(self.task_id, round)

    @asynccontextmanager
    async def report_error_context(self):
        try:
            yield
        except get_cancelled_exc_class() as e:
            raise
        except TaskError as e:
            if not e.retry:
                await self._report_error()
            raise
        except Exception as e:
            await self._report_error()

    @property
    def lock(self) -> Lock:
        if self._lock is None:
            self._lock = Lock()
        return self._lock

    async def process_event(self, event: models.TaskEvent):
        async with self.report_error_context():
            with wrap_task_error():
                async with self.lock:
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

    async def task_created(self, event: models.TaskCreated):
        async with self.state_context():
            assert self._state is not None, "The task runner has not been initialized."
            assert (
                self._state.status == models.TaskStatus.Pending
            ), "Task status is not pending when receive event TaskCreated."

            self._state.round = event.round

            task = await self.relay.get_task(event.task_id)

            if self.distributed:

                def run_distributed_task():
                    from h_server.celery_app import get_celery

                    celery = get_celery()
                    kwargs = {
                        "task_id": task.task_id,
                        "prompts": task.prompt,
                        "base_model": task.base_model,
                        "lora_model": task.lora_model,
                        "distributed": True,
                    }
                    if task.task_config is not None:
                        kwargs["task_config"] = task.task_config.model_dump()
                    if task.pose is not None:
                        kwargs["pose"] = task.pose.model_dump()
                    res: AsyncResult = celery.send_task(
                        self.task_name,
                        kwargs=kwargs,
                    )
                    try:
                        res.get()
                    except celery_exceptions.CeleryError:
                        raise
                    except Exception as e:
                        _logger.exception(e)
                        raise TaskFailure(str(e))

                await to_thread.run_sync(run_distributed_task, cancellable=True)
                self._state.status = models.TaskStatus.Executing

            else:

                def run_local_task():
                    import h_worker.task as h_task
                    from h_worker.task.utils import get_image_hash

                    assert self.local_config is not None

                    task_func = getattr(h_task, self.task_name)
                    kwargs = {
                        "task_id": task.task_id,
                        "prompts": task.prompt,
                        "base_model": task.base_model,
                        "lora_model": task.lora_model,
                        "distributed": False,
                        "local_config": self.local_config.model_dump(),
                    }
                    if task.task_config is not None:
                        kwargs["task_config"] = task.task_config.model_dump()
                    if task.pose is not None:
                        kwargs["pose"] = task.pose.model_dump()

                    task_func(**kwargs)

                    image_dir = os.path.join(
                        self.local_config.data_dir, "image", str(self.task_id)
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
                self._state.status = models.TaskStatus.Executing
                await self.queue.put(next_event)

    async def result_ready(self, event: models.TaskResultReady):
        async with self.state_context():
            assert self._state is not None, "The task runner has not been initialized."
            assert (
                self._state.status == models.TaskStatus.Executing
            ), "Task status is not executing when receive event TaskResultReady."

            result, commitment, nonce = make_result_commitments(event.hashes)
            await self.contracts.task_contract.submit_task_result_commitment(
                task_id=self.task_id,
                round=self._state.round,
                commitment=commitment,
                nonce=nonce,
            )

            self._state.status = models.TaskStatus.ResultUploaded
            self._state.files = event.files
            self._state.result = result

    async def commitment_ready(self, event: models.TaskResultCommitmentsReady):
        async with self.state_context():
            assert self._state is not None, "The task runner has not been initialized."
            assert (
                self._state.status == models.TaskStatus.ResultUploaded
            ), "Task status is not result_uploaded when receive event TaskResultCommitmentsReady."
            assert (
                len(self._state.result) > 0
            ), "Task result not found when receive event TaskResultCommitmentsReady."
            await self.contracts.task_contract.disclose_task_result(
                task_id=self.task_id, round=self._state.round, result=self._state.result
            )

            self._state.status = models.TaskStatus.Disclosed

        self.watcher.unwatch_event(self._commitment_watch_id)

    async def task_success(self, event: models.TaskSuccess):
        async with self.state_context():
            assert self._state is not None, "The task runner has not been initialized."
            assert (
                self._state.status == models.TaskStatus.Disclosed
            ), "Task status is not disclosed when receive event TaskSuccess."

            if event.result_node == self.contracts.account:
                await self.relay.upload_task_result(self.task_id, self._state.files)

            self._state.status = models.TaskStatus.Success

        await self.cleanup()

    async def task_aborted(self, event: models.TaskAborted):
        async with self.state_context():
            assert self._state is not None, "The task runner has not been initialized."

            self._state.status = models.TaskStatus.Aborted

        await self.cleanup()

    async def cleanup(self):
        assert self._state is not None, "The task runner has not been initialized."
        assert (
            self._state.status == models.TaskStatus.Success
            or self._state.status == models.TaskStatus.Aborted
        ), "Task status is not success or aborted when shutdown."

        self.watcher.unwatch_event(self._success_watch_id)
        self.watcher.unwatch_event(self._aborted_watch_id)

        def delete_result_files(files: List[str]):
            assert len(files) > 0
            dirname = os.path.dirname(files[0])
            if os.path.exists(dirname):
                shutil.rmtree(dirname)

        with fail_after(5, shield=True):
            await to_thread.run_sync(delete_result_files, self._state.files)
            await self.cache.delete(task_id=self.task_id)


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

        self._state: Optional[models.TaskState] = None
        self._lock: Optional[Lock] = None

    async def init(self):
        assert self._state is None, "The task runner has already been initialized."

        try:
            state = await self.cache.load(self.task_id)
            self._state = state
        except KeyError:
            self._state = models.TaskState(
                task_id=self.task_id,
                round=0,
                status=models.TaskStatus.Pending,
            )

    @asynccontextmanager
    async def state_context(self):
        try:
            yield
        finally:
            if self._state is not None:
                with fail_after(5, shield=True):
                    await self.cache.dump(task_state=self._state)

    @property
    def lock(self) -> Lock:
        if self._lock is None:
            self._lock = Lock()
        return self._lock

    async def process_event(self, event: models.TaskEvent):
        with wrap_task_error():
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
        async with self.state_context():
            assert self._state is not None
            assert self._state.status == models.TaskStatus.Pending

            self._state.round = event.round
            self._state.status = models.TaskStatus.Executing

    async def result_ready(self, event: models.TaskResultReady):
        async with self.state_context():
            assert self._state is not None
            assert self._state.status == models.TaskStatus.Executing

            self._state.files = event.files
            self._state.result = b"".join([bytes.fromhex(h[2:]) for h in event.hashes])
            self._state.status = models.TaskStatus.ResultUploaded

    async def commitment_ready(self, event: models.TaskResultCommitmentsReady):
        async with self.state_context():
            assert self._state is not None
            assert self._state.status == models.TaskStatus.ResultUploaded

            self._state.status = models.TaskStatus.Disclosed

    async def task_success(self, event: models.TaskSuccess):
        async with self.state_context():
            assert self._state is not None
            assert self._state.status == models.TaskStatus.Disclosed

            self._state.status = models.TaskStatus.Success

        await self.cleanup()

    async def task_aborted(self, event: models.TaskAborted):
        async with self.state_context():
            assert self._state is not None
            self._state.status = models.TaskStatus.Aborted

        await self.cleanup()

    async def cleanup(self):
        assert self._state is not None
        self._state = None
        with fail_after(5, shield=True):
            await self.cache.delete(task_id=self.task_id)
