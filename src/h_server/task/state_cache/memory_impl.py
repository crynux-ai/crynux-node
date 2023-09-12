from datetime import datetime
from typing import Dict, Optional, Set

from h_server.models import TaskState, TaskStatus

from .abc import TaskStateCache


class MemoryTaskStateCache(TaskStateCache):
    def __init__(self) -> None:
        self._states: Dict[int, TaskState] = {}
        self._deleted_states: Dict[int, TaskState] = {}
        self._state_times: Dict[int, datetime] = {}

    async def load(self, task_id: int) -> TaskState:
        if task_id in self._states:
            return self._states[task_id]
        else:
            raise KeyError(f"Task state of {task_id} not found.")

    async def dump(self, task_state: TaskState):
        if task_state.task_id in self._deleted_states:
            raise KeyError(f"Task state of {task_state.task_id} has been deleted.")
        self._states[task_state.task_id] = task_state
        self._state_times[task_state.task_id] = datetime.now()

    async def has(self, task_id: int) -> bool:
        return task_id in self._states

    async def delete(self, task_id: int):
        if task_id in self._states:
            state = self._states.pop(task_id)
            self._deleted_states[task_id] = state

    async def count(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        deleted: Optional[bool] = None,
        status: Optional[TaskStatus] = None,
    ):
        if deleted is not None:
            if deleted:
                states = self._deleted_states
            else:
                states = self._states
        else:
            states = {**self._deleted_states, **self._states}

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
                if state.status == status
            }
        return len(states)
