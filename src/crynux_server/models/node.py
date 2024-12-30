from typing import List
from enum import Enum, IntEnum

from pydantic import BaseModel


class ChainNodeStatus(IntEnum):
    QUIT = 0
    AVAILABLE = 1
    BUSY = 2
    PENDING_PAUSE = 3
    PENDING_QUIT = 4
    PAUSED = 5


class GpuInfo(BaseModel):
    name: str
    vram: int


class ChainNodeInfo(BaseModel):
    status: ChainNodeStatus
    gpu_id: bytes
    gpu: GpuInfo
    score: int
    version: List[int]
    public_key: bytes
    last_model_ids: List[str]
    local_model_ids: List[str]


class ChainNetworkNodeInfo(BaseModel):
    node_address: str
    gpu_model: str
    vram: int


class NodeStatus(Enum):
    Init = "initializing"
    Running = "running"
    Paused = "paused"
    Stopped = "stopped"
    Error = "error"
    PendingPause = "pending_pause"
    PendingStop = "pending_stop"


def convert_node_status(chain_status: ChainNodeStatus) -> NodeStatus:
    if chain_status == ChainNodeStatus.QUIT:
        return NodeStatus.Stopped
    elif chain_status in [ChainNodeStatus.AVAILABLE, ChainNodeStatus.BUSY]:
        return NodeStatus.Running
    elif chain_status == ChainNodeStatus.PAUSED:
        return NodeStatus.Paused
    elif chain_status == ChainNodeStatus.PENDING_PAUSE:
        return NodeStatus.PendingPause
    elif chain_status == ChainNodeStatus.PENDING_QUIT:
        return NodeStatus.PendingStop
    else:
        raise ValueError(f"unknown ChainNodeStatus: {chain_status}")


class NodeState(BaseModel):
    status: NodeStatus
    message: str = ""
    init_message: str = ""
