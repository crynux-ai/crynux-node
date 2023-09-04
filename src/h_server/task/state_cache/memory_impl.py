from typing import Dict, Set

from h_server.models import TaskState

from .abc import TaskStateCache


class MemoryTaskStateCache(TaskStateCache):
    def __init__(self) -> None:
        self._states: Dict[int, TaskState] = {}
        self._deleted_tasks: Set[int] = set()

    async def load(self, task_id: int) -> TaskState:
        if task_id in self._states:
            return self._states[task_id]
        else:
            raise KeyError(f"Task state of {task_id} not found.")

    async def dump(self, task_state: TaskState):
        if task_state.task_id in self._deleted_tasks:
            raise KeyError(f"Task state of {task_state.task_id} has been deleted.")
        self._states[task_state.task_id] = task_state

    async def has(self, task_id: int) -> bool:
        return task_id in self._states

    async def delete(self, task_id: int):
        if task_id in self._states:
            del self._states[task_id]
            self._deleted_tasks.add(task_id)
