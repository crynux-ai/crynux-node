import json
import logging
import subprocess
from contextlib import contextmanager
from typing import AsyncGenerator, Dict, Optional, Union

from anyio import sleep

from crynux_server.config import Config, get_config

from .error import PrefetchError, TaskError
from .exchange import TaskExchange
from .task import TaskInput, TaskResult, TaskStreamResult
from .utils import get_exe_head

_logger = logging.getLogger(__name__)


class WorkerManager(object):
    def __init__(self, config: Optional[Config] = None) -> None:
        if config is None:
            config = get_config()
        self.config = config

        self._exchange = TaskExchange()

        self._next_worker_id = 1
        # store worker current TaskResult, when it is None means worker is idle
        # when current worker id equals 0, means the worker has disconnected
        self._current_task: Union[TaskResult, TaskStreamResult, None] = None
        self._current_worker_id = 0

        self._prefetch_task_result = TaskStreamResult()
        self._init_inference_task_result = TaskResult()

        self._prefetch_worker_id: Optional[int] = None
        self._init_inference_worker_id: Optional[int] = None

        self._worker_process: Optional[subprocess.Popen] = None

        self._version: Optional[str] = None

    @contextmanager
    def start(self):
        if self.config.task_config is not None:
            script_dir = self.config.task_config.script_dir
            patch_url = self.config.task_config.worker_patch_url
            version_file = self.config.task_config.worker_version_file
            hf_cache_dir = self.config.task_config.hf_cache_dir
            external_cache_dir = self.config.task_config.external_cache_dir
        else:
            script_dir = ""
            patch_url = ""
            version_file = "version.txt"
            hf_cache_dir = ""
            external_cache_dir = ""

        args = get_exe_head(script_dir)
        envs = {
            "CRYNUX_WORKER_PATCH_URL": patch_url,
            "CRYNUX_WORKER_VERSION_FILE": version_file,
            "cw_data_dir__models__huggingface": hf_cache_dir,
            "cw_data_dir__models__external": external_cache_dir,
        }
        if (
            self.config.task_config is not None
            and self.config.task_config.preloaded_models is not None
        ):
            envs["cw_preloaded_models"] = (
                self.config.task_config.preloaded_models.model_dump_json()
            )
        if (
            self.config.task_config is not None
            and self.config.task_config.proxy is not None
        ):
            envs["cw_proxy"] = self.config.task_config.proxy.model_dump_json()

        node_url = f"ws://127.0.0.1:{self.config.server_port}/manager/v1/worker/"
        envs["cw_node_url"] = node_url

        log_config = {"dir": self.config.log.dir, "level": self.config.log.level}
        envs["cw_log"] = json.dumps(log_config)

        with subprocess.Popen(args=args, env=envs):
            yield

    def connect(self, version: str) -> int:
        worker_id = self._next_worker_id
        self._next_worker_id += 1
        self._current_worker_id = worker_id
        self._version = version
        return worker_id

    def disconnect(self, worker_id: int):
        assert (
            worker_id == self._current_worker_id
        ), f"Worker {worker_id} is disconnected"
        # cancel the worker's running task
        if self._current_task is not None and not self._current_task.done():
            self._current_task.cancel()
            self._current_task = None

        self._current_worker_id = 0

    async def send_task(self, input: TaskInput):
        return await self._exchange.send_task(input)

    async def get_task(self, worker_id: int):
        await sleep(0)
        assert (
            worker_id == self._current_worker_id
        ), f"Worker {worker_id} is disconnected"
        assert self._current_task is None, f"Worker {worker_id} is busy now"
        task_input, task_result = await self._exchange.get_task()

        def done_callback(_):
            # mark worker status idle when worker is connected
            if worker_id == self._current_worker_id:
                self._current_task = None

        task_result.add_done_callback(done_callback)

        self._current_task = task_result
        return task_input, task_result

    def start_prefetch_task(self, worker_id: int):
        assert (
            worker_id == self._current_worker_id
        ), f"Worker {worker_id} is disconnected"
        assert self._current_task is None, f"Worker {worker_id} is busy now"

        if self._prefetch_worker_id is None and not self._prefetch_task_result.done():
            self._current_task = self._prefetch_task_result
            self._prefetch_worker_id = worker_id

            def done_callback(_):
                # mark worker status idle when worker is connected
                if worker_id == self._current_worker_id:
                    self._current_task = None
                self._prefetch_worker_id = None
                _logger.info("finish prefetch task")

            self._prefetch_task_result.add_done_callback(done_callback)

    async def push_prefetch_task_progress(self, worker_id: int, progress: str):
        if (
            self._prefetch_worker_id == worker_id
            and not self._prefetch_task_result.done()
        ):
            await self._prefetch_task_result.push_result(progress)

    def prefetch_task_error(self, worker_id: int, err_msg: str):
        if (
            self._prefetch_worker_id == worker_id
            and not self._prefetch_task_result.done()
        ):
            self._prefetch_task_result.set_error(PrefetchError(err_msg))

    def finish_prefetch_task(self, worker_id: int):
        if (
            self._prefetch_worker_id == worker_id
            and not self._prefetch_task_result.done()
        ):
            self._prefetch_task_result.close()

    def reset_prefetch_task(self):
        self._prefetch_task_result = TaskStreamResult()

    async def get_prefetch_task_progress(self) -> AsyncGenerator[str, None]:
        if not self._prefetch_task_result.done():
            async for progress in self._prefetch_task_result.get():
                yield progress

    def start_init_inference_task(self, worker_id: int):
        assert (
            worker_id == self._current_worker_id
        ), f"Worker {worker_id} is disconnected"
        assert self._current_task is None, f"Worker {worker_id} is busy now"

        if not self._init_inference_task_result.done():
            self._current_task = self._init_inference_task_result
            self._init_inference_worker_id = worker_id

            def done_callback(_):
                # mark worker status idle when worker is connected
                if worker_id == self._current_worker_id:
                    self._current_task = None
                self._init_inference_worker_id = None
                _logger.info("finish init inference task")

            self._init_inference_task_result.add_done_callback(done_callback)

    def init_inference_task_success(self, worker_id: int):
        if (
            self._init_inference_worker_id == worker_id
            and not self._init_inference_task_result.done()
        ):
            self._init_inference_task_result.set_result(None)

    def init_inference_task_error(self, worker_id: int, err_msg: str):
        if (
            self._init_inference_worker_id == worker_id
            and not self._init_inference_task_result.done()
        ):
            self._init_inference_task_result.set_error(TaskError(err_msg))

    async def get_init_inference_task_result(self):
        if not self._init_inference_task_result.done():
            await self._init_inference_task_result.get()

    def reset_init_inference_task(self):
        self._init_inference_task_result = TaskResult()


_default_worker_manager: Optional[WorkerManager] = None


def get_worker_manager():
    assert _default_worker_manager is not None

    return _default_worker_manager


def set_worker_manager(worker_manager: WorkerManager):
    global _default_worker_manager

    _default_worker_manager = worker_manager
