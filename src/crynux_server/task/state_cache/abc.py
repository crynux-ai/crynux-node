from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List

from crynux_server import models


class TaskStateCache(ABC):
    @abstractmethod
    async def load(self, task_id_commitment: bytes) -> models.TaskState:
        ...

    @abstractmethod
    async def dump(self, task_state: models.TaskState):
        ...

    @abstractmethod
    async def has(self, task_id_commitment: bytes) -> bool:
        ...

    @abstractmethod
    async def find(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        status: Optional[List[models.TaskStatus]] = None
    ) -> List[models.TaskState]:
        ...
