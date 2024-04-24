from typing import TYPE_CHECKING, Optional, Union

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3
from web3.contract.async_contract import AsyncContractEvent

from crynux_server.models import ChainTask, TaskType

from .utils import ContractWrapper, TxWaiter
from .w3_pool import W3Pool

if TYPE_CHECKING:
    from crynux_server.config import TxOption


__all__ = ["TaskContract"]


class TaskContract(ContractWrapper):
    def __init__(
        self, w3_pool: W3Pool, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3_pool, "Task", contract_address)

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
        w3: Optional[AsyncWeb3] = None
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
            w3=w3,
        )

    async def get_selected_node(
        self, task_hash: Union[str, bytes], data_hash: Union[str, bytes], round: int, *, w3: Optional[AsyncWeb3] = None
    ) -> str:
        return await self._function_call(
            "getSelectedNode", taskHash=task_hash, dataHash=data_hash, round=round, w3=w3
        )

    async def submit_task_result_commitment(
        self,
        task_id: int,
        round: int,
        commitment: bytes,
        nonce: bytes,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "submitTaskResultCommitment",
            option=option,
            taskId=task_id,
            round=round,
            commitment=commitment,
            nonce=nonce,
            w3=w3
        )

    async def disclose_task_result(
        self,
        task_id: int,
        round: int,
        result: Union[str, bytes],
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "discloseTaskResult",
            option=option,
            taskId=task_id,
            round=round,
            result=result,
            w3=w3
        )

    async def report_results_uploaded(
        self, task_id: int, round: int, *, option: "Optional[TxOption]" = None, w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "reportResultsUploaded",
            option=option,
            taskId=task_id,
            round=round,
            w3=w3
        )

    async def report_task_error(
        self, task_id: int, round: int, *, option: "Optional[TxOption]" = None, w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "reportTaskError",
            option=option,
            taskId=task_id,
            round=round,
            w3=w3
        )

    async def cancel_task(
        self, task_id: int, *, option: "Optional[TxOption]" = None, w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "cancelTask",
            option=option,
            taskId=task_id,
            w3=w3
        )

    async def update_distance_threshold(
        self, threshold: int, *, option: "Optional[TxOption]" = None, w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateDistanceThreshold",
            option=option,
            threshold=threshold,
            w3=w3
        )

    async def update_timeout(
        self, timeout: int, *, option: "Optional[TxOption]" = None, w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "updateTimeout",
            option=option,
            t=timeout,
            w3=w3
        )

    async def get_task(self, task_id: int, *, w3: Optional[AsyncWeb3] = None) -> ChainTask:
        res = await self._function_call("getTask", taskId=task_id, w3=w3)
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
            commitment_submit_rounds=res[10],
            results=res[11],
            result_disclosed_rounds=res[12],
            result_node=res[13],
            aborted=res[14],
            timeout=res[15],
        )

    async def get_node_task(self, address: str, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("getNodeTask", nodeAddress=address, w3=w3)
