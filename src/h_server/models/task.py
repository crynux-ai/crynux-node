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
    result_node: str


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
    prompt: str
    base_model: str
    lora_model: str
    task_config: Optional[TaskConfig] = None
    pose: Optional[PoseConfig] = None


class RelayTaskInput(BaseModel):
    task_id: int
    base_model: str
    prompt: str
    task_config: TaskConfig
    pose: PoseConfig
    lora_model: str = ""


class TaskStatus(Enum):
    Pending = "pending"
    Executing = "executing"
    ResultUploaded = "result_uploaded"
    Disclosed = "disclosed"
    Success = "success"
    Aborted = "aborted"
    Error = "error"


class TaskState(BaseModel):
    task_id: int
    round: int
    status: TaskStatus
    files: List[str] = []
    result: bytes = b""
