from asyncio import Queue
from collections import deque, defaultdict
from typing import Optional, Dict, Deque, DefaultDict, Tuple

from anyio import Event
from pydantic import BaseModel

from crynux_server.models import TaskType


class TaskInput(BaseModel):
    task_name: str
    task_type: TaskType
    task_args: str
    task_id: int = 0


class TaskCancelled(Exception):
    pass


class TaskError(Exception):
    def __init__(self, err_msg: str) -> None:
        self.err_msg = err_msg

    def __str__(self) -> str:
        return f"TaskError: {self.err_msg}"


class TaskResult(object):
    def __init__(self) -> None:
        self._done_event = Event()

        self._result = None
        self._error: Optional[Exception] = None

    def set_result(self, result):
        assert not self._done_event.is_set(), "TaskReuslt is done"
        self._result = result
        self._done_event.set()

    def set_error(self, err_msg: str):
        assert not self._done_event.is_set(), "TaskReuslt is done"
        self._error = TaskError(err_msg)
        self._done_event.set()

    def cancel(self):
        assert not self._done_event.is_set(), "TaskReuslt is done"
        self._error = TaskCancelled()
        self._done_event.set()

    async def get(self):
        await self._done_event.wait()
        if self._error is not None:
            raise self._error
        return self._result



DEFAULT_ROUTING_KEY = ""


class TaskExchange(object):
    def __init__(self) -> None:
        self._worker_task_queues: Dict[int, Queue[Tuple[TaskInput, TaskResult]]] = {}
        
        self._worker_routing_key: Dict[int, str] = {}
        self._worker_route_map: DefaultDict[str, Deque[int]] = defaultdict(lambda: deque())
        self._used_worker_queue: Deque[int] = deque()

    def register(self, worker_id: int):
        self._worker_task_queues[worker_id] = Queue()
        
        self._worker_routing_key[worker_id] = DEFAULT_ROUTING_KEY
        self._worker_route_map[DEFAULT_ROUTING_KEY].appendleft(worker_id)
        self._used_worker_queue.appendleft(worker_id)

    def unregister(self, worker_id: int):
        task_queue = self._worker_task_queues[worker_id]
        while not task_queue.empty():
            _, result = task_queue.get_nowait()
            result.cancel()

        routing_key = self._worker_routing_key.pop(worker_id)
        self._worker_route_map[routing_key].remove(worker_id)
        self._used_worker_queue.remove(worker_id)

    async def send_task(self, task_input: TaskInput, routing_key: str = DEFAULT_ROUTING_KEY):
        # should called by task runner
        # try sending task to worker without routing key first
        # if all workers has a routing key, try sending task to a worker with the same routing key
        # if no worker has the same routing key, then send task to the least recent used worker

        assert len(self._worker_task_queues) > 0, "No workers in the task exchange"

        result = TaskResult()

        if len(self._worker_route_map[DEFAULT_ROUTING_KEY]) > 0:
            worker_id = self._worker_route_map[DEFAULT_ROUTING_KEY].popleft()
            self._used_worker_queue.remove(worker_id)
        elif routing_key != DEFAULT_ROUTING_KEY and len(self._worker_route_map[routing_key]) > 0:
            worker_id = self._worker_route_map[routing_key].popleft()
            self._used_worker_queue.remove(worker_id)
        else:
            worker_id = self._used_worker_queue.popleft()
            worker_routing_key = self._worker_routing_key[worker_id]
            # the global most recent used worker should be the most recent used worker among the same routing key
            _worker_id = self._worker_route_map[worker_routing_key].popleft()
            assert worker_id == _worker_id

        task_queue = self._worker_task_queues[worker_id]
        await task_queue.put((task_input, result))
        self._worker_route_map[routing_key].append(worker_id)
        self._used_worker_queue.append(worker_id)

    async def get_task(self, worker_id: int) -> Tuple[TaskInput, TaskResult]:
        # should called by worker
        assert worker_id in self._worker_task_queues, f"worker id {worker_id} not found in task exchange"
        queue = self._worker_task_queues[worker_id]
        return await queue.get()


