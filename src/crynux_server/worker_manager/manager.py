from typing import AsyncGenerator, Dict, Optional, Union

from .exchange import TaskExchange
from .task import TaskInput, TaskResult, TaskStreamResult
from .error import TaskError, PrefetchError


class WorkerManager(object):
    def __init__(self) -> None:
        self._exchange = TaskExchange()

        self._next_worker_id = 0
        # store worker current TaskResult, when it is None means worker is idle
        # when worker not in the dict, means it is disconnected
        self._worker_task: Dict[int, Union[TaskResult, TaskStreamResult, None]] = {}

        self._prefetch_task_result = TaskStreamResult()
        self._init_inference_task_result = TaskResult()

        self._prefetch_worker_id: Optional[int] = None
        self._init_inference_worker_id: Optional[int] = None

    def connect(self) -> int:
        worker_id = self._next_worker_id
        self._next_worker_id += 1
        self._worker_task[worker_id] = None
        return worker_id

    def disconnect(self, worker_id: int):
        assert worker_id in self._worker_task, f"Worker {worker_id} is disconnected"
        # cancel the worker's running task
        task_result = self._worker_task.pop(worker_id)
        if task_result is not None and not task_result.done():
            task_result.cancel()

    async def send_task(self, input: TaskInput):
        return await self._exchange.send_task(input)

    async def get_task(self, worker_id: int):
        assert worker_id in self._worker_task, f"Worker {worker_id} is disconnected"
        assert self._worker_task[worker_id] is None, f"Worker {worker_id} is busy now"
        task_input, task_result = await self._exchange.get_task()

        def done_callback(_):
            # mark worker status idle when worker is connected
            if worker_id in self._worker_task:
                self._worker_task[worker_id] = None

        task_result.add_done_callback(done_callback)

        self._worker_task[worker_id] = task_result
        return task_input, task_result
    
    def start_prefetch_task(self, worker_id: int):
        assert worker_id in self._worker_task, f"Worker {worker_id} is disconnected"
        assert self._worker_task[worker_id] is None, f"Worker {worker_id} is busy now"

        if self._prefetch_worker_id is None and not self._prefetch_task_result.done():
            self._worker_task[worker_id] = self._prefetch_task_result
            self._prefetch_worker_id = worker_id

            def done_callback(_):
                # mark worker status idle when worker is connected
                if worker_id in self._worker_task:
                    self._worker_task[worker_id] = None
                self._prefetch_worker_id = None

            self._prefetch_task_result.add_done_callback(done_callback)

    async def push_prefetch_task_progress(self, worker_id: int, progress: str):
        if self._prefetch_worker_id == worker_id and not self._prefetch_task_result.done():
            await self._prefetch_task_result.push_result(progress)

    def prefetch_task_error(self, worker_id: int, err_msg: str):
        if self._prefetch_worker_id == worker_id and not self._prefetch_task_result.done():
            self._prefetch_task_result.set_error(PrefetchError(err_msg))

    def finish_prefetch_task(self, worker_id: int):
        if self._prefetch_worker_id == worker_id and not self._prefetch_task_result.done():
            self._prefetch_task_result.close()

    def reset_prefetch_task(self):
        self._prefetch_task_result = TaskStreamResult()


    async def get_prefetch_task_progress(self) -> AsyncGenerator[str, None]:
        if not self._prefetch_task_result.done():
            async for progress in self._prefetch_task_result.get():
                yield progress

    def start_init_inference_task(self, worker_id: int):
        assert worker_id in self._worker_task, f"Worker {worker_id} is disconnected"
        assert self._worker_task[worker_id] is None, f"Worker {worker_id} is busy now"

        if not self._init_inference_task_result.done():
            self._worker_task[worker_id] = self._init_inference_task_result
            self._init_inference_worker_id = worker_id

            def done_callback(_):
                # mark worker status idle when worker is connected
                if worker_id in self._worker_task:
                    self._worker_task[worker_id] = None
                self._init_inference_worker_id = None

            self._init_inference_task_result.add_done_callback(done_callback)

    def init_inference_task_success(self, worker_id: int):
        if self._init_inference_worker_id == worker_id and not self._init_inference_task_result.done():
            self._init_inference_task_result.set_result(None)

    def init_inference_task_error(self, worker_id: int, err_msg: str):
        if self._init_inference_worker_id == worker_id and not self._init_inference_task_result.done():
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
