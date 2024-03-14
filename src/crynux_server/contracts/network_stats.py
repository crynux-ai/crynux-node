from typing import TYPE_CHECKING, List, Optional

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3

from crynux_server.models import ChainNetworkNodeInfo

from .utils import ContractWrapperBase, TxWaiter

if TYPE_CHECKING:
    from crynux_server.config import TxOption

__all__ = ["NetworkStatsContract"]


class NetworkStatsContract(ContractWrapperBase):
    def __init__(
        self, w3: AsyncWeb3, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3, "NetworkStats", contract_address)

    async def total_nodes(self) -> int:
        return await self._function_call("totalNodes")

    async def active_nodes(self) -> int:
        return await self._function_call("activeNodes")

    async def available_nodes(self) -> int:
        return await self._function_call("availableNodes")

    async def busy_nodes(self) -> int:
        return await self._function_call("busyNodes")

    async def total_tasks(self) -> int:
        return await self._function_call("totalTasks")

    async def queued_tasks(self) -> int:
        return await self._function_call("queuedTasks")

    async def running_tasks(self) -> int:
        return await self._function_call("runningTasks")

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

    async def get_all_node_info(
        self, offset: int, length: int
    ) -> List[ChainNetworkNodeInfo]:
        nodes = await self._function_call(
            "getAllNodeInfo", offset=offset, length=length
        )
        res = []
        for node in nodes:
            res.append(
                ChainNetworkNodeInfo(
                    node_address=node[0], gpu_model=node[1], vram=node[2]
                )
            )
        return res
