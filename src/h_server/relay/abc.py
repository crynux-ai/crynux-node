from abc import ABC, abstractmethod
from typing import List, BinaryIO

from h_server.models import RelayTask, RelayTaskInput


class Relay(ABC):
    @abstractmethod
    async def create_task(self, task: RelayTaskInput) -> RelayTask:
        ...

    @abstractmethod
    async def get_task(self, task_id: int) -> RelayTask:
        ...

    @abstractmethod
    async def upload_task_result(self, task_id: int, file_paths: List[str]):
        ...

    @abstractmethod
    async def get_result(self, task_id: int, image_num: int, dst: BinaryIO):
        ...

    @abstractmethod
    async def close(self):
        ...
