from datetime import datetime
from typing import Dict, Optional, Set

from h_server.models import TaskState

from .abc import TaskStateCache


class MemoryTaskStateCache(TaskStateCache):
    def __init__(self) -> None:
        self._states: Dict[int, TaskState] = {}
        self._deleted_tasks: Set[int] = set()
        self._state_times: Dict[int, datetime] = {}

    async def load(self, task_id: int) -> TaskState:
        if task_id in self._states:
            return self._states[task_id]
        else:
            raise KeyError(f"Task state of {task_id} not found.")

    async def dump(self, task_state: TaskState):
        if task_state.task_id in self._deleted_tasks:
            raise KeyError(f"Task state of {task_state.task_id} has been deleted.")
        self._states[task_state.task_id] = task_state
        self._state_times[task_state.task_id] = datetime.now()

    async def has(self, task_id: int) -> bool:
        return task_id in self._states

    async def delete(self, task_id: int):
        if task_id in self._states:
            del self._states[task_id]
            self._deleted_tasks.add(task_id)

    async def count(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        deleted: Optional[bool] = None,
    ):
        state_times = self._state_times
        if start is not None:
            state_times = {
                task_id: t for task_id, t in state_times.items() if t >= start
            }
        if end is not None:
            state_times = {task_id: t for task_id, t in state_times.items() if t < end}
        if deleted is not None:
            if deleted:
                state_times = {
                    task_id: t
                    for task_id, t in state_times.items()
                    if task_id in self._deleted_tasks
                }
            else:
                state_times = {
                    task_id: t
                    for task_id, t in state_times.items()
                    if task_id not in self._deleted_tasks
                }
        return len(state_times)
