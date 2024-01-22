from abc import ABC, abstractmethod
from typing import List, BinaryIO

from crynux_server.models import RelayTask


class Relay(ABC):
    @abstractmethod
    async def create_task(self, task_id: int, task_args: str) -> RelayTask:
        ...

    @abstractmethod
    async def get_task(self, task_id: int) -> RelayTask:
        ...

    @abstractmethod
    async def upload_task_result(self, task_id: int, file_paths: List[str]):
        ...

    @abstractmethod
    async def get_result(self, task_id: int, index: int, dst: BinaryIO):
        ...

    @abstractmethod
    async def close(self):
        ...
