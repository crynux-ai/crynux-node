import json
import logging
import os
import subprocess
from contextlib import asynccontextmanager, contextmanager
from typing import Dict, Optional

import psutil
from anyio import Condition, fail_after, sleep

from crynux_server.config import Config, get_config
from crynux_server.models import TaskInput

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
            worker_pid_file = self.config.task_config.worker_pid_file
        else:
            script_dir = ""
            patch_url = ""
            hf_cache_dir = ""
            external_cache_dir = ""
            output_dir = ""
            worker_pid_file = "crynux_worker.pid"

        args = get_exe_head(script_dir)
        envs = os.environ.copy()
        envs.update(
            {
                "CRYNUX_WORKER_PATCH_URL": patch_url,
                "cw_data_dir__models__huggingface": hf_cache_dir,
                "cw_data_dir__models__external": external_cache_dir,
                "cw_output_dir": output_dir,
                "cw_pid_file": worker_pid_file
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

        # kill the old worker process if it is still alive
        if os.path.exists(worker_pid_file):
            with open(worker_pid_file, mode="r", encoding="utf-8") as f:
                pid = int(f.read().strip())
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                for proc in process.children(recursive=True):
                    proc.kill()
                process.kill()

        p = subprocess.Popen(args=args, env=envs)
        self._worker_process = p
        
        # Check if process is still alive immediately after start
        if p.poll() is not None:
            # Process has already terminated
            raise RuntimeError(f"Worker process failed to start. Exit code: {p.returncode}")
        
        try:
            yield
        finally:
            if self._worker_process is not None:
                process = psutil.Process(self._worker_process.pid)
                for proc in process.children(recursive=True):
                    proc.kill()
                process.kill()
                self._worker_process = None

    def is_worker_process_alive(self) -> bool:
        """
        Check if the worker process is still alive.
        Returns True if process is running, False otherwise.
        """
        if self._worker_process is None:
            return False
        return self._worker_process.poll() is None

    def get_worker_process_exit_code(self) -> Optional[int]:
        """
        Get the exit code of the worker process.
        Returns None if process is still running, otherwise returns the exit code.
        """
        if self._worker_process is None:
            return None
        return self._worker_process.poll()

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
    async def wait_connected(self, timeout: Optional[float] = None):
        with fail_after(timeout):
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

        return task_input, task_future

    @contextmanager
    def task_future(self, worker_id: int, task_id_commitment: str):
        assert (
            worker_id == self._current_worker_id
        ), f"Worker {worker_id} is disconnected"
        assert task_id_commitment in self._task_futures, f"No such task future {task_id_commitment}"

        fut = self._task_futures[task_id_commitment]
        try:
            yield fut
        finally:
            if fut.done():
                del self._task_futures[task_id_commitment]

_default_worker_manager: Optional[WorkerManager] = None


def get_worker_manager():
    assert _default_worker_manager is not None

    return _default_worker_manager


def set_worker_manager(worker_manager: WorkerManager):
    global _default_worker_manager

    _default_worker_manager = worker_manager
