from enum import Enum, IntEnum
from typing import List

from pydantic import BaseModel


class TaskType(IntEnum):
    SD = 0
    LLM = 1
    SD_FT_LORA = 2

class ChainTask(BaseModel):
    id: int
    task_type: TaskType
    creator: str
    task_hash: bytes
    data_hash: bytes
    vram_limit: int
    is_success: bool
    selected_nodes: List[str]
    commitments: List[bytes]
    nonces: List[bytes]
    commitment_submit_rounds: List[int]
    results: List[bytes]
    result_disclosed_rounds: List[int]
    result_node: str
    aborted: bool
    timeout: int


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
    task_id: int
    creator: str
    task_hash: str
    data_hash: str
    task_args: str


class TaskStatus(Enum):
    Pending = "pending"
    Executing = "executing"
    ResultUploaded = "result_uploaded"
    Disclosed = "disclosed"
    ResultFileUploaded = "result_file_uploaded"
    Success = "success"
    Aborted = "aborted"


class TaskState(BaseModel):
    task_id: int
    round: int
    timeout: int
    status: TaskStatus
    files: List[str] = []
    result: bytes = b""
    disclosed: bool = False
    waiting_tx_hash: bytes = b""
    waiting_tx_method: str = ""
    checkpoint: str = ""
