from collections import deque
from typing import Deque, Tuple

from anyio import Condition
from crynux_server.models import TaskInput

from .task import TaskResult


class TaskExchange(object):
    def __init__(self) -> None:
        self._condition = Condition()
        self._task_queue: Deque[Tuple[TaskInput, TaskResult]] = deque()

    async def send_task(self, task_input: TaskInput):
        task_result = TaskResult()

        async with self._condition:
            self._task_queue.append((task_input, task_result))
            self._condition.notify(1)
        return task_result

    async def get_task(self) -> Tuple[TaskInput, TaskResult]:
        async with self._condition:
            while len(self._task_queue) == 0:
                await self._condition.wait()
            return self._task_queue.popleft()
