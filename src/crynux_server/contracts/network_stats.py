from typing import TYPE_CHECKING, List, Optional

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3

from crynux_server.models import ChainNetworkNodeInfo

from .utils import ContractWrapper, TxWaiter
from .w3_pool import W3Pool

if TYPE_CHECKING:
    from crynux_server.config import TxOption

__all__ = ["NetworkStatsContract"]


class NetworkStatsContract(ContractWrapper):
    def __init__(
        self, w3_pool: W3Pool, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3_pool, "NetworkStats", contract_address)

    async def total_nodes(self, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("totalNodes", w3=w3)

    async def active_nodes(self, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("activeNodes", w3=w3)

    async def available_nodes(self, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("availableNodes", w3=w3)

    async def busy_nodes(self, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("busyNodes", w3=w3)

    async def total_tasks(self, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("totalTasks", w3=w3)

    async def queued_tasks(self, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("queuedTasks", w3=w3)

    async def running_tasks(self, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("runningTasks", w3=w3)

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

    async def get_all_node_info(
        self, offset: int, length: int, w3: Optional[AsyncWeb3] = None
    ) -> List[ChainNetworkNodeInfo]:
        nodes = await self._function_call(
            "getAllNodeInfo", offset=offset, length=length, w3=w3
        )
        res = []
        for node in nodes:
            res.append(
                ChainNetworkNodeInfo(
                    node_address=node[0], gpu_model=node[1], vram=node[2]
                )
            )
        return res
