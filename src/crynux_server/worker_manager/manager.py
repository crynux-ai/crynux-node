import json
import logging
import os
import subprocess
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Dict, Optional, Union

import psutil
from anyio import Condition, sleep

from crynux_server.config import Config, get_config
from crynux_server.models import TaskInput

from .error import TaskDownloadError, TaskError
from .exchange import TaskExchange
from .task import TaskFuture
from .utils import get_exe_head

_logger = logging.getLogger(__name__)


class WorkerManager(object):
    def __init__(self, config: Optional[Config] = None) -> None:
        if config is None:
            config = get_config()
        self.config = config

        self._exchange = TaskExchange()

        self._next_worker_id = 1
        self._task_futures: Dict[str, TaskFuture] = {}
        self._current_worker_id = 0

        self._worker_process: Optional[subprocess.Popen] = None

        self._version: Optional[str] = None

        self._connect_condition = Condition()

    @property
    def version(self):
        return self._version

    @contextmanager
    def start(self):
        if self.config.task_config is not None:
            script_dir = self.config.task_config.script_dir
            patch_url = self.config.task_config.worker_patch_url
            hf_cache_dir = self.config.task_config.hf_cache_dir
            external_cache_dir = self.config.task_config.external_cache_dir
            output_dir = self.config.task_config.output_dir
        else:
            script_dir = ""
            patch_url = ""
            hf_cache_dir = ""
            external_cache_dir = ""
            output_dir = ""

        args = get_exe_head(script_dir)
        envs = os.environ.copy()
        envs.update(
            {
                "CRYNUX_WORKER_PATCH_URL": patch_url,
                "cw_data_dir__models__huggingface": hf_cache_dir,
                "cw_data_dir__models__external": external_cache_dir,
                "cw_output_dir": output_dir,
            }
        )
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

        p = subprocess.Popen(args=args, env=envs)
        try:
            yield
        finally:
            process = psutil.Process(p.pid)
            for proc in process.children(recursive=True):
                proc.kill()
            process.kill()

    async def connect(self, version: str) -> int:
        worker_id = self._next_worker_id
        self._next_worker_id += 1
        async with self._connect_condition:
            self._current_worker_id = worker_id
            self._version = version
            self._connect_condition.notify_all()
        return worker_id

    async def disconnect(self, worker_id: int):
        assert (
            worker_id == self._current_worker_id
        ), f"Worker {worker_id} is disconnected"
        # cancel the worker's running task
        for task_result in self._task_futures.values():
            if not task_result.done():
                task_result.cancel()
        self._task_futures.clear()

        async with self._connect_condition:
            self._current_worker_id = 0
            self._version = None
            self._connect_condition.notify_all()

    async def is_connected(self) -> bool:
        return self._current_worker_id > 0

    @asynccontextmanager
    async def wait_connected(self):
        async with self._connect_condition:
            while self._current_worker_id == 0:
                await self._connect_condition.wait()
            yield

    @asynccontextmanager
    async def wait_connection_changed(self):
        async with self._connect_condition:
            await self._connect_condition.wait()
            yield

    async def send_task(self, input: TaskInput):
        return await self._exchange.send_task(input)

    async def get_task(self, worker_id: int):
        await sleep(0)
        assert (
            worker_id == self._current_worker_id
        ), f"Worker {worker_id} is disconnected"
        task_input, task_future = await self._exchange.get_task()
        task_id_commitment = task_input.task.task_id
        self._task_futures[task_id_commitment] = task_future

        def done_callback(_):
            if worker_id == self._current_worker_id:
                del self._task_futures[task_id_commitment]

        task_future.add_done_callback(done_callback)

        return task_input, task_future

    def get_task_future(self, worker_id: int, task_id_commitment: str) -> TaskFuture:
        assert (
            worker_id == self._current_worker_id
        ), f"Worker {worker_id} is disconnected"
        return self._task_futures[task_id_commitment]


_default_worker_manager: Optional[WorkerManager] = None


def get_worker_manager():
    assert _default_worker_manager is not None

    return _default_worker_manager


def set_worker_manager(worker_manager: WorkerManager):
    global _default_worker_manager

    _default_worker_manager = worker_manager
