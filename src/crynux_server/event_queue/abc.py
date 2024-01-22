from abc import ABC, abstractmethod
from typing import Tuple

from crynux_server.models import TaskEvent


class EventQueue(ABC):
    @abstractmethod
    async def put(self, event: TaskEvent):
        ...

    @abstractmethod
    async def get(self) -> Tuple[int, TaskEvent]:
        ...

    @abstractmethod
    async def ack(self, ack_id: int):
        ...

    @abstractmethod
    async def no_ack(self, ack_id: int):
        ...
