from abc import ABC, abstractmethod
from typing import BinaryIO, List, Optional

from crynux_server.models import RelayTask


class Relay(ABC):
    @abstractmethod
    async def create_task(self, task_id_commitment: bytes, task_args: str) -> RelayTask: ...

    @abstractmethod
    async def get_task(self, task_id_commitment: bytes) -> RelayTask: ...

    @abstractmethod
    async def upload_checkpoint(self, task_id_commitment: bytes, checkpoint_dir: str): ...

    @abstractmethod
    async def get_checkpoint(self, task_id_commitment: bytes, result_checkpoint_dir: str): ...

    @abstractmethod
    async def upload_task_result(
        self, task_id_commitment: bytes, file_paths: List[str], checkpoint_dir: Optional[str] = None
    ): ...

    @abstractmethod
    async def get_result(self, task_id_commitment: bytes, index: int, dst: BinaryIO): ...

    @abstractmethod
    async def get_result_checkpoint(self, task_id_commitment: bytes, result_checkpoint_dir: str): ...

    @abstractmethod
    async def now(self) -> int: ...

    @abstractmethod
    async def close(self): ...
