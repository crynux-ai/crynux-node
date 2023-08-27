from abc import ABC, abstractmethod

from h_server import models


class TaskStateCache(ABC):
    @abstractmethod
    async def load(self, task_id: int) -> models.TaskState:
        ...
    
    @abstractmethod
    async def dump(self, task_state: models.TaskState):
        ...

    @abstractmethod
    async def has(self, task_id: int) -> bool:
        ...

    @abstractmethod
    async def delete(self, task_id: int):
        ...
