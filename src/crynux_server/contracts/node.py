from typing import TYPE_CHECKING, List, Optional

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3

from crynux_server.models import ChainNodeInfo, ChainNodeStatus, GpuInfo

from .utils import ContractWrapperBase, TxWaiter

if TYPE_CHECKING:
    from crynux_server.config import TxOption


__all__ = ["NodeContract"]


class NodeContract(ContractWrapperBase):
    def __init__(
        self, w3: AsyncWeb3, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3, "Node", contract_address)

    async def join(
        self, gpu_name: str, gpu_vram: int, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "join", gpuName=gpu_name, gpuVram=gpu_vram, option=option
        )

    async def quit(self, *, option: "Optional[TxOption]" = None) -> TxWaiter:
        return await self._transaction_call("quit", option=option)

    async def pause(self, *, option: "Optional[TxOption]" = None) -> TxWaiter:
        return await self._transaction_call("pause", option=option)

    async def resume(self, *, option: "Optional[TxOption]" = None) -> TxWaiter:
        return await self._transaction_call("resume", option=option)

    async def update_task_contract_address(
        self, address: str, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateTaskContractAddress", option=option, taskContract=address
        )

    async def get_node_status(self, address: str) -> ChainNodeStatus:
        res = await self._function_call("getNodeStatus", nodeAddress=address)
        return ChainNodeStatus(res)

    async def get_node_info(self, address: str) -> ChainNodeInfo:
        res = await self._function_call("getNodeInfo", nodeAddress=address)
        info = ChainNodeInfo(
            status=ChainNodeStatus(res[0]),
            gpu_id=res[1],
            gpu=GpuInfo(name=res[2][0], vram=res[2][1]),
        )
        return info

    async def get_available_nodes(self) -> List[str]:
        res = await self._function_call("getAvailableNodes")
        return res

    async def get_available_gpus(self) -> List[GpuInfo]:
        res = await self._function_call("getAvailableGPUs")
        return [GpuInfo(name=item[0], vram=item[1]) for item in res]
