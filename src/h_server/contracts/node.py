from typing import TYPE_CHECKING, Optional

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3

from h_server.models import ChainNodeStatus

from .utils import ContractWrapperBase, TxWaiter

if TYPE_CHECKING:
    from h_server.config import TxOption


__all__ = ["NodeContract"]


class NodeContract(ContractWrapperBase):
    def __init__(
        self, w3: AsyncWeb3, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3, "Node", contract_address)

    async def join(self, *, option: "Optional[TxOption]" = None) -> TxWaiter:
        return await self._transaction_call("join", option=option)

    async def quit(self, *, option: "Optional[TxOption]" = None) -> TxWaiter:
        return await self._transaction_call("quit", option=option)

    async def pause(self, *, option: "Optional[TxOption]" = None) -> TxWaiter:
        return await self._transaction_call("pause", option=option)

    async def resume(self, *, option: "Optional[TxOption]" = None) -> TxWaiter:
        return await self._transaction_call("resume", option=option)

    async def total_nodes(self) -> int:
        return await self._function_call("totalNodes")

    async def available_nodes(self) -> int:
        return await self._function_call("availableNodes")

    async def update_task_contract_address(
        self, address: str, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateTaskContractAddress", option=option, taskContract=address
        )

    async def get_node_status(self, address: str) -> ChainNodeStatus:
        res = await self._function_call("getNodeStatus", nodeAddress=address)
        return ChainNodeStatus(res)
