from typing import TYPE_CHECKING, Any, Dict, Optional, Union, cast

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3
from web3.contract.async_contract import AsyncContractEvent

from h_server.models import ChainTask

from .utils import ContractWrapperBase, TxWaiter

if TYPE_CHECKING:
    from h_server.config import TxOption


__all__ = ["TaskContract"]


class TaskContract(ContractWrapperBase):
    def __init__(
        self, w3: AsyncWeb3, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3, "Task", contract_address)

    async def create_task(
        self,
        task_hash: Union[str, bytes],
        data_hash: Union[str, bytes],
        *,
        option: "Optional[TxOption]" = None,
    ) -> TxWaiter:
        return await self._transaction_call(
            "createTask", option=option, taskHash=task_hash, dataHash=data_hash
        )

    async def get_selected_node(
        self, task_hash: Union[str, bytes], data_hash: Union[str, bytes], round: int
    ) -> str:
        return await self._function_call(
            "getSelectedNode", taskHash=task_hash, dataHash=data_hash, round=round
        )

    async def submit_task_result_commitment(
        self,
        task_id: int,
        round: int,
        commitment: bytes,
        nonce: bytes,
        *,
        option: "Optional[TxOption]" = None,
    ) -> TxWaiter:
        return await self._transaction_call(
            "submitTaskResultCommitment",
            option=option,
            taskId=task_id,
            round=round,
            commitment=commitment,
            nonce=nonce,
        )

    async def disclose_task_result(
        self,
        task_id: int,
        round: int,
        result: Union[str, bytes],
        *,
        option: "Optional[TxOption]" = None,
    ) -> TxWaiter:
        return await self._transaction_call(
            "discloseTaskResult",
            option=option,
            taskId=task_id,
            round=round,
            result=result,
        )

    async def report_results_uploaded(
        self, task_id: int, round: int, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "reportResultsUploaded",
            option=option,
            taskId=task_id,
            round=round,
        )

    async def report_task_error(
        self, task_id: int, round: int, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "reportTaskError",
            option=option,
            taskId=task_id,
            round=round,
        )

    async def get_task(self, task_id: int) -> ChainTask:
        res = await self._function_call("getTask", taskId=task_id)
        return ChainTask(
            id=res[0],
            creator=res[1],
            task_hash=res[2],
            data_hash=res[3],
            is_success=res[4],
            selected_nodes=res[5],
            commitments=res[6],
            nonces=res[7],
            results=res[8],
            result_disclosed_rounds=res[9],
            result_node=res[10]
        )

    async def get_node_task(self, address: str) -> int:
        return await self._function_call("getNodeTask", nodeAddress=address)

    async def get_events(
        self,
        event_name: str,
        filter_args: Optional[Dict[str, Any]] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
    ):
        event = self.contract.events[event_name]
        event = cast(AsyncContractEvent, event)
        events = await event.get_logs(
            argument_filters=filter_args, fromBlock=from_block, toBlock=to_block
        )
        return list(events)
