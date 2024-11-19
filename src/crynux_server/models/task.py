from enum import IntEnum
from typing import List

from pydantic import BaseModel


class TaskType(IntEnum):
    SD = 0
    LLM = 1
    SD_FT_LORA = 2


class TaskError(IntEnum):
    NONE = 0
    ParametersValidationFailed = 1


class TaskAbortReason(IntEnum):
    NONE = 0
    Timeout = 1
    ModelDownloadFailed = 2
    IncorrectResult = 3
    TaskFeeTooLow = 4


class TaskStatus(IntEnum):
    Queued = 0
    Started = 1
    ParametersUploaded = 2
    ErrorReported = 3
    ScoreReady = 4
    Validated = 5
    GroupValidated = 6
    EndInvalidated = 7
    EndSuccess = 8
    EndAborted = 9
    EndGroupRefund = 10
    EndGroupSuccess = 11


class ChainTask(BaseModel):
    task_type: TaskType
    creator: str
    task_id_commitment: bytes
    sampling_seed: bytes
    nonce: bytes
    sequence: int
    status: TaskStatus
    selected_node: str
    timeout: int
    score: bytes
    task_fee: int
    task_size: int
    model_id: str
    min_vram: int
    required_gpu: str
    required_gpu_vram: int
    task_version: str
    abort_reason: TaskAbortReason
    error: TaskError
    payment_addresses: List[str]
    payments: List[int]
    start_blocknum: int
    finish_blocknum: int


class TaskConfig(BaseModel):
    image_width: int
    image_height: int
    lora_weight: int
    num_images: int
    seed: int
    steps: int


class PoseConfig(BaseModel):
    pose_weight: int
    preprocess: bool
    data_url: str = ""


class RelayTask(BaseModel):
    task_id_commitment: bytes
    creator: str
    task_args: str


class TaskState(BaseModel):
    task_id_commitment: bytes
    timeout: int
    status: TaskStatus
    task_type: TaskType
    files: List[str] = []
    score: bytes = b""
    waiting_tx_hash: bytes = b""
    waiting_tx_method: str = ""
    checkpoint: str = ""
