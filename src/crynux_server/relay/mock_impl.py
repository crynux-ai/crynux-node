import os
import shutil
from contextlib import contextmanager
from tempfile import mkdtemp
from typing import BinaryIO, Dict, List, Optional

from anyio import Condition, get_cancelled_exc_class, to_thread

from crynux_server.models import RelayTask
from crynux_server.utils import get_task_hash

from .abc import Relay
from .exceptions import RelayError


class MockRelay(Relay):
    def __init__(self) -> None:
        super().__init__()

        self.tasks: Dict[int, RelayTask] = {}

        self.task_input_checkpoint: Dict[int, str] = {}

        self.task_results: Dict[int, List[str]] = {}
        self.task_result_checkpoint: Dict[int, str] = {}

        self._conditions: Dict[int, Condition] = {}

        self._tempdir = mkdtemp()

        self._closed = False

    def get_condition(self, task_id: int) -> Condition:
        if task_id not in self._conditions:
            self._conditions[task_id] = Condition()
        return self._conditions[task_id]

    @contextmanager
    def wrap_error(self, method: str):
        try:
            yield
        except KeyboardInterrupt:
            raise
        except get_cancelled_exc_class():
            raise
        except Exception as e:
            raise RelayError(status_code=500, method=method, message=str(e))

    async def create_task(self, task_id: int, task_args: str) -> RelayTask:
        with self.wrap_error("createTask"):
            t = RelayTask(
                task_id=task_id,
                creator="",
                task_hash=get_task_hash(task_args),
                data_hash="",
                task_args=task_args,
            )
            self.tasks[task_id] = t
            return t

    async def upload_checkpoint(self, task_id: int, checkpoint_dir: str):
        with self.wrap_error("uploadCheckpoint"):
            condition = self.get_condition(task_id=task_id)
            async with condition:
                task_dir = os.path.join(self._tempdir, str(task_id))
                if not os.path.exists(task_dir):
                    os.makedirs(task_dir, exist_ok=True)

                dst_path = os.path.join(task_dir, "input_checkpoint")
                await to_thread.run_sync(shutil.copytree, checkpoint_dir, dst_path)
                self.task_input_checkpoint[task_id] = dst_path
                condition.notify()

    async def get_checkpoint(self, task_id: int, result_checkpoint_dir: str):
        with self.wrap_error("getCheckpoint"):
            condition = self.get_condition(task_id=task_id)
            async with condition:
                while task_id not in self.task_input_checkpoint:
                    await condition.wait()
                
                src_path = self.task_input_checkpoint[task_id]
                await to_thread.run_sync(shutil.copytree, src_path, result_checkpoint_dir)

    async def get_task(self, task_id: int) -> RelayTask:
        with self.wrap_error("getTask"):
            return self.tasks[task_id]

    async def upload_task_result(self, task_id: int, file_paths: List[str], checkpoint_dir: Optional[str] = None):
        with self.wrap_error("uploadTaskResult"):
            condition = self.get_condition(task_id=task_id)
            async with condition:
                self.task_results[task_id] = []

                task_dir = os.path.join(self._tempdir, str(task_id))
                if not os.path.exists(task_dir):
                    os.makedirs(task_dir, exist_ok=True)

                for src_path in file_paths:
                    filename = os.path.basename(src_path)
                    dst_path = os.path.join(task_dir, filename)

                    await to_thread.run_sync(shutil.copyfile, src_path, dst_path)
                    self.task_results[task_id].append(dst_path)

                if checkpoint_dir is not None:
                    dst_path = os.path.join(task_dir, "result_checkpoint")

                    await to_thread.run_sync(shutil.copytree, checkpoint_dir, dst_path)
                    self.task_result_checkpoint[task_id] = dst_path

                condition.notify()

    async def get_result(self, task_id: int, index: int, dst: BinaryIO):
        with self.wrap_error("getResult"):
            condition = self.get_condition(task_id=task_id)
            async with condition:
                while task_id not in self.task_results:
                    await condition.wait()

            src_file = self.task_results[task_id][index]

            def _copy_file_obj():
                with open(src_file, mode="rb") as src:
                    shutil.copyfileobj(src, dst)

            await to_thread.run_sync(_copy_file_obj)

    async def get_result_checkpoint(self, task_id: int, result_checkpoint_dir: str):
        with self.wrap_error("getResultCheckpoint"):
            condition = self.get_condition(task_id=task_id)
            async with condition:
                while task_id not in self.task_result_checkpoint:
                    await condition.wait()

            src_dir = self.task_result_checkpoint[task_id]

            await to_thread.run_sync(shutil.copytree, src_dir, result_checkpoint_dir)

    async def close(self):
        if not self._closed:
            self.tasks = {}
            self.task_results = {}
            self._conditions = {}

            def _rm_tempdir():
                if os.path.exists(self._tempdir):
                    shutil.rmtree(self._tempdir)

            await to_thread.run_sync(_rm_tempdir)
            self._closed = True
