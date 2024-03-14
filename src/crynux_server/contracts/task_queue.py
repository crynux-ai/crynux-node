from typing import TYPE_CHECKING, Optional

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3

from .utils import ContractWrapperBase, TxWaiter

if TYPE_CHECKING:
    from crynux_server.config import TxOption


class TaskQueueContract(ContractWrapperBase):
    def __init__(
        self, w3: AsyncWeb3, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3, "TaskQueue", contract_address)

    async def update_task_contract_address(
        self, address: str, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateTaskContractAddress", option=option, taskContract=address
        )

    async def update_size_limit(
        self, limit: int, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateSizeLimit", option=option, limit=limit
        )

    async def size(self) -> int:
        return await self._function_call("size")

    async def get_size_limit(self) -> int:
        return await self._function_call("getSizeLimit")

    async def include(self, task_id: int) -> bool:
        return await self._function_call("include", taskId=task_id)