from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class ChainTask(BaseModel):
    id: int
    creator: str
    task_hash: bytes
    data_hash: bytes
    is_success: bool
    selected_nodes: List[str]
    commitments: List[bytes]
    nonces: List[bytes]
    results: List[bytes]
    result_disclosed_rounds: List[int]


class TaskConfig(BaseModel):
    image_width: int
    image_height: int
    lora_weight: float
    num_images: int
    seed: int
    steps: int


class PoseConfig(BaseModel):
    data_url: str
    pose_weight: float
    preprocess: bool


class RelayTask(BaseModel):
    task_id: int
    creator: str
    task_hash: str
    data_hash: str
    prompt: str
    base_model: str
    lora_model: str
    task_config: Optional[TaskConfig] = None
    pose: Optional[PoseConfig] = None


class TaskStatus(Enum):
    Pending = "pending"
    Executing = "executing"
    ResultUploaded = "result_uploaded"
    Disclosed = "disclosed"
    Success = "success"
    Aborted = "aborted"


class TaskState(BaseModel):
    task_id: int
    round: int
    status: TaskStatus
    files: List[str] = []
    result: bytes = b""
