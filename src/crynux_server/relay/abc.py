from abc import ABC, abstractmethod
from typing import BinaryIO, List, Optional

from crynux_server.models import RelayTask


class Relay(ABC):
    @abstractmethod
    async def create_task(self, task_id: int, task_args: str) -> RelayTask: ...

    @abstractmethod
    async def get_task(self, task_id: int) -> RelayTask: ...

    @abstractmethod
    async def upload_checkpoint(self, task_id: int, checkpoint_dir: str): ...

    @abstractmethod
    async def get_checkpoint(self, task_id: int, result_checkpoint_dir: str): ...

    @abstractmethod
    async def upload_task_result(
        self, task_id: int, file_paths: List[str], checkpoint_dir: Optional[str] = None
    ): ...

    @abstractmethod
    async def get_result(self, task_id: int, index: int, dst: BinaryIO): ...

    @abstractmethod
    async def get_result_checkpoint(self, task_id: int, result_checkpoint_dir: str): ...

    @abstractmethod
    async def close(self): ...
