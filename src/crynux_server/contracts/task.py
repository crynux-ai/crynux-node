from typing import TYPE_CHECKING, Any, Dict, Optional, Union, cast

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3
from web3.contract.async_contract import AsyncContractEvent

from crynux_server.models import ChainTask, TaskType

from .utils import ContractWrapperBase, TxWaiter

if TYPE_CHECKING:
    from crynux_server.config import TxOption


__all__ = ["TaskContract"]


class TaskContract(ContractWrapperBase):
    def __init__(
        self, w3: AsyncWeb3, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3, "Task", contract_address)

    async def create_task(
        self,
        task_type: TaskType,
        task_hash: Union[str, bytes],
        data_hash: Union[str, bytes],
        vram_limit: int,
        task_fee: int,
        cap: int,
        *,
        option: "Optional[TxOption]" = None,
    ) -> TxWaiter:
        return await self._transaction_call(
            "createTask",
            option=option,
            taskType=task_type,
            taskHash=task_hash,
            dataHash=data_hash,
            vramLimit=vram_limit,
            taskFee=task_fee,
            cap=cap,
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

    async def cancel_task(
        self, task_id: int, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "cancelTask",
            option=option,
            taskId=task_id,
        )

    async def update_distance_threshold(
        self, threshold: int, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateDistanceThreshold",
            option=option,
            threshold=threshold,
        )

    async def update_timeout(
        self, timeout: int, *, option: "Optional[TxOption]" = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateTimeout",
            option=option,
            t=timeout,
        )

    async def get_task(self, task_id: int) -> ChainTask:
        res = await self._function_call("getTask", taskId=task_id)
        return ChainTask(
            id=res[0],
            task_type=res[1],
            creator=res[2],
            task_hash=res[3],
            data_hash=res[4],
            vram_limit=res[5],
            is_success=res[6],
            selected_nodes=res[7],
            commitments=res[8],
            nonces=res[9],
            results=res[10],
            result_disclosed_rounds=res[11],
            result_node=res[12],
            aborted=res[13],
            timeout=res[14],
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
