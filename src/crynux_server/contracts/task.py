from typing import TYPE_CHECKING, Optional, Union

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3
from web3.contract.async_contract import AsyncContractEvent

from crynux_server.models import (
    ChainTask,
    TaskType,
    TaskError,
    TaskAbortReason,
    TaskStatus,
)

from .utils import ContractWrapper, TxWaiter
from .w3_pool import W3Pool

if TYPE_CHECKING:
    from crynux_server.config import TxOption


__all__ = ["TaskContract"]


class TaskContract(ContractWrapper):
    def __init__(
        self, w3_pool: W3Pool, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3_pool, "VSSTask", contract_address)

    # interfaces for owner
    async def set_relay_address(
        self,
        address: str,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ):
        return await self._transaction_call(
            "setRelayAddress", addr=address, option=option, w3=w3
        )

    async def update_distance_threshold(
        self,
        threshold: int,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ):
        return await self._transaction_call(
            "updateDistanceThreshold", threshold=threshold, option=option, w3=w3
        )

    async def update_timeout(
        self,
        timeout: int,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ):
        return await self._transaction_call(
            "updateTimeout", t=timeout, option=option, w3=w3
        )

    # Interfaces for applications
    async def create_task(
        self,
        task_fee: int,
        task_type: TaskType,
        task_id_commitment: bytes,
        nonce: bytes,
        model_id: str,
        min_vram: int,
        required_gpu: str,
        required_gpu_vram: int,
        task_version: str,
        task_size: int,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ):
        return await self._transaction_call(
            "createTask",
            taskType=task_type,
            taskIDCommitment=task_id_commitment,
            nonce=nonce,
            modelID=model_id,
            minimumVRAM=min_vram,
            requiredGPU=required_gpu,
            requiredGPUVRAM=required_gpu_vram,
            taskVersion=task_version,
            taskSize=task_size,
            value=task_fee,
            option=option,
            w3=w3,
        )

    async def validate_single_task(
        self,
        task_id_commitment: bytes,
        vrf_proof: bytes,
        public_key: bytes,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ):
        return await self._transaction_call(
            "validateSingleTask",
            taskIDCommitment=task_id_commitment,
            vrfProof=vrf_proof,
            publicKey=public_key,
            option=option,
            w3=w3,
        )

    async def validate_task_group(
        self,
        task_id_commitment1: bytes,
        task_id_commitment2: bytes,
        task_id_commitment3: bytes,
        task_id: bytes,
        vrf_proof: bytes,
        public_key: bytes,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ):
        return await self._transaction_call(
            "validateTaskGroup",
            taskIDCommitment1=task_id_commitment1,
            taskIDCommitment2=task_id_commitment2,
            taskIDCommitment3=task_id_commitment3,
            taskGUID=task_id,
            vrfProof=vrf_proof,
            publicKey=public_key,
            option=option,
            w3=w3,
        )

    # Interfaces for nodes
    async def report_task_error(
        self,
        task_id_commitment: bytes,
        error: TaskError,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ):
        return await self._transaction_call(
            "reportTaskError",
            taskIDCommitment=task_id_commitment,
            error=error,
            option=option,
            w3=w3,
        )

    async def submit_task_score(
        self,
        task_id_commitment: bytes,
        score: bytes,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ):
        return await self._transaction_call(
            "submitTaskScore",
            taskIDCommitment=task_id_commitment,
            taskScore=score,
            option=option,
            w3=w3,
        )

    # Interfaces for both applications and nodes
    async def abort_task(
        self,
        task_id_commitment: bytes,
        abort_reason: TaskAbortReason,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ):
        return await self._transaction_call(
            "abortTask",
            taskIDCommitment=task_id_commitment,
            abortReason=abort_reason,
            option=option,
            w3=w3,
        )

    async def get_task(
        self, task_id_commitment: bytes, *, w3: Optional[AsyncWeb3] = None
    ):
        res = await self._function_call(
            "getTask",
            taskIDCommitment=task_id_commitment,
            w3=w3,
        )
        task = ChainTask(
            task_type=TaskType(res[0]),
            creator=res[1],
            task_id_commitment=res[2],
            sampling_seed=res[3],
            nonce=res[4],
            sequence=res[5],
            status=TaskStatus(res[6]),
            selected_node=res[7],
            timeout=res[8],
            score=res[9],
            task_fee=res[10],
            task_size=res[11],
            task_model_id=res[12],
            min_vram=res[13],
            required_gpu=res[14],
            required_gpu_vram=res[15],
            task_version=res[16],
            abort_reason=TaskAbortReason(res[17]),
            error=TaskError(res[18]),
            payment_addresses=res[19],
            payments=res[20],
            create_timestamp=res[21],
            start_timestamp=res[22],
            score_ready_timestamp=res[23],
        )
        return task

    async def get_node_task(
        self, address: str, *, w3: Optional[AsyncWeb3] = None
    ) -> bytes:
        res = await self._function_call("getNodeTask", nodeAddress=address, w3=w3)
        return res

    # Interfaces for Relay
    async def report_task_parameters_uploaded(
        self,
        task_id_commitment: bytes,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ):
        return await self._transaction_call(
            "reportTaskParametersUploaded",
            taskIDCommitment=task_id_commitment,
            option=option,
            w3=w3,
        )

    async def report_task_result_uploaded(
        self,
        task_id_commitment: bytes,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ):
        return await self._transaction_call(
            "reportTaskResultUploaded",
            taskIDCommitment=task_id_commitment,
            option=option,
            w3=w3,
        )
