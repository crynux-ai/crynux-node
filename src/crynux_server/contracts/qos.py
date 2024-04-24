from typing import TYPE_CHECKING, Optional

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3

from .utils import ContractWrapper, TxWaiter
from .w3_pool import W3Pool

if TYPE_CHECKING:
    from crynux_server.config import TxOption


class QOSContract(ContractWrapper):
    def __init__(
        self, w3_pool: W3Pool, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3_pool, "QOS", contract_address)

    async def update_task_contract_address(
        self, address: str, *, option: "Optional[TxOption]" = None, w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateTaskContractAddress", option=option, taskContract=address, w3=w3
        )

    async def update_node_contract_address(
        self, address: str, *, option: "Optional[TxOption]" = None, w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateNodeContractAddress", option=option, nodeContract=address, w3=w3
        )

    async def update_kickout_threshold(
        self, threshold: int, *, option: "Optional[TxOption]" = None, w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateKickoutThreshold", option=option, threshold=threshold, w3=w3
        )

    async def get_task_count(self, address: str, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("getTaskCount", nodeAddress=address, w3=w3)

    async def get_task_score(self, address: str, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("getTaskScore", nodeAddress=address, w3=w3)

    async def get_recent_task_score(self, address: str, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("getRecentTaskScore", nodeAddress=address, w3=w3)

    async def get_recent_task_count(self, address: str, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("getRecentTaskCount", nodeAddress=address, w3=w3)

    async def get_current_task_score(self, address: str, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("getCurrentTaskScore", nodeAddress=address, w3=w3)

    async def get_task_score_limit(self, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("getTaskScoreLimit", w3=w3)
