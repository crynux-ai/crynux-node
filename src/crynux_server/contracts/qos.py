from typing import TYPE_CHECKING, Optional

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3

from .utils import ContractWrapperBase, TxWaiter

if TYPE_CHECKING:
    from crynux_server.config import TxOption


class QOSContract(ContractWrapperBase):
    def __init__(
        self, w3: AsyncWeb3, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3, "QOS", contract_address)

    async def update_task_contract_address(
        self, address: str, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateTaskContractAddress", option=option, taskContract=address
        )

    async def update_node_contract_address(
        self, address: str, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateNodeContractAddress", option=option, nodeContract=address
        )

    async def update_kickout_threshold(
        self, threshold: int, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateKickoutThreshold", option=option, threshold=threshold
        )

    async def get_task_count(self, address: str) -> int:
        return await self._function_call("getTaskCount", nodeAddress=address)

    async def get_task_score(self, address: str) -> int:
        return await self._function_call("getTaskScore", nodeAddress=address)

    async def get_recent_task_score(self, address: str) -> int:
        return await self._function_call("getRecentTaskScore", nodeAddress=address)

    async def get_recent_task_count(self, address: str) -> int:
        return await self._function_call("getRecentTaskCount", nodeAddress=address)

    async def get_current_task_score(self, address: str) -> int:
        return await self._function_call("getCurrentTaskScore", nodeAddress=address)

    async def get_task_score_limit(self) -> int:
        return await self._function_call("getTaskScoreLimit")
