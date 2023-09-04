from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

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

    @abstractmethod
    async def count(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        deleted: Optional[bool] = None,
        status: Optional[models.TaskStatus] = None
    ) -> int:
        ...
