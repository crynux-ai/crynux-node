from typing import TYPE_CHECKING, Optional

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3

from .utils import ContractWrapper, TxWaiter
from .w3_pool import W3Pool

if TYPE_CHECKING:
    from crynux_server.config import TxOption


class TaskQueueContract(ContractWrapper):
    def __init__(
        self, w3_pool: W3Pool, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3_pool, "TaskQueue", contract_address)

    async def update_task_contract_address(
        self, address: str, *, option: "Optional[TxOption]" = None, w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateTaskContractAddress", option=option, taskContract=address, w3=w3
        )

    async def update_size_limit(
        self, limit: int, *, option: "Optional[TxOption]" = None, w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateSizeLimit", option=option, limit=limit, w3=w3
        )

    async def size(self, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("size", w3=w3)

    async def get_size_limit(self, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("getSizeLimit", w3=w3)

    async def include(self, task_id: int, *, w3: Optional[AsyncWeb3] = None) -> bool:
        return await self._function_call("include", taskId=task_id, w3=w3)