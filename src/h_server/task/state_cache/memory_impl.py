from datetime import datetime
from typing import Dict, Optional, List

from h_server.models import TaskState, TaskStatus

from .abc import TaskStateCache


class MemoryTaskStateCache(TaskStateCache):
    def __init__(self) -> None:
        self._states: Dict[int, TaskState] = {}
        self._state_times: Dict[int, datetime] = {}

    async def load(self, task_id: int) -> TaskState:
        if task_id in self._states:
            return self._states[task_id]
        else:
            raise KeyError(f"Task state of {task_id} not found.")

    async def dump(self, task_state: TaskState):
        self._states[task_state.task_id] = task_state
        self._state_times[task_state.task_id] = datetime.now()

    async def has(self, task_id: int) -> bool:
        return task_id in self._states

    async def find(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        status: Optional[List[TaskStatus]] = None,
    ):
        states = self._states
        if start is not None:
            states = {
                task_id: state
                for task_id, state in states.items()
                if self._state_times[task_id] >= start
            }
        if end is not None:
            states = {
                task_id: state
                for task_id, state in states.items()
                if self._state_times[task_id] < end
            }
        if status is not None:
            states = {
                task_id: state
                for task_id, state in states.items()
                if state.status in status
            }
        return list(states.values())
