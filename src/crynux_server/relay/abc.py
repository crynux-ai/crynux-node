from abc import ABC, abstractmethod
from datetime import datetime
from typing import BinaryIO, List, Optional

from eth_typing import ChecksumAddress

from crynux_server.models import (ChainNodeStatus, Event, EventType, NodeInfo,
                                  RelayTask, TaskAbortReason, TaskError)


class Relay(ABC):
    @property
    @abstractmethod
    def node_address(self) -> ChecksumAddress: ...

    """ task related """

    @abstractmethod
    async def create_task(
        self,
        task_id_commitment: bytes,
        task_args: str,
        checkpoint_dir: Optional[str] = None,
    ) -> RelayTask: ...

    @abstractmethod
    async def get_task(self, task_id_commitment: bytes) -> RelayTask: ...

    @abstractmethod
    async def get_checkpoint(
        self, task_id_commitment: bytes, result_checkpoint_dir: str
    ): ...

    @abstractmethod
    async def report_task_error(
        self, task_id_commitment: bytes, task_error: TaskError
    ): ...

    @abstractmethod
    async def submit_task_score(self, task_id_commitment: bytes, score: bytes): ...

    @abstractmethod
    async def abort_task(
        self, task_id_commitment: bytes, abort_reason: TaskAbortReason
    ): ...

    @abstractmethod
    async def upload_task_result(
        self,
        task_id_commitment: bytes,
        file_paths: List[str],
        checkpoint_dir: Optional[str] = None,
    ): ...

    @abstractmethod
    async def get_result(
        self, task_id_commitment: bytes, index: int, dst: BinaryIO
    ): ...

    @abstractmethod
    async def get_result_checkpoint(
        self, task_id_commitment: bytes, result_checkpoint_dir: str
    ): ...

    """ auxiliary """

    @abstractmethod
    async def now(self) -> int: ...

    @abstractmethod
    async def close(self): ...

    """ node related """

    @abstractmethod
    async def node_get_node_info(self) -> NodeInfo: ...

    @abstractmethod
    async def node_get_node_status(self) -> ChainNodeStatus: ...

    @abstractmethod
    async def node_join(
        self, gpu_name: str, gpu_vram: int, model_ids: List[str], version: str
    ): ...

    @abstractmethod
    async def node_report_model_downloaded(self, model_id: str): ...

    @abstractmethod
    async def node_pause(self): ...

    @abstractmethod
    async def node_quit(self): ...

    @abstractmethod
    async def node_resume(self): ...

    @abstractmethod
    # returns task_id_commitment
    async def node_get_current_task(self) -> bytes: ...

    @abstractmethod
    async def node_update_version(self, version: str): ...

    """ balance related """

    @abstractmethod
    async def get_balance(self) -> int: ...

    @abstractmethod
    async def transfer(self, amount: int, to_addr: str): ...

    @abstractmethod
    async def get_events(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        event_type: Optional[EventType] = None,
        node_address: Optional[str] = None,
        task_id_commitment: Optional[bytes] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> List[Event]: ...
