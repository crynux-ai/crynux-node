from enum import Enum, IntEnum

from pydantic import BaseModel


class ChainNodeStatus(IntEnum):
    QUIT = 0
    AVAILABLE = 1
    BUSY = 2
    PENDING_PAUSE = 3
    PENDING_QUIT = 4
    PAUSED = 5


class NodeStatus(Enum):
    Init = "initializing"
    Running = "running"
    Paused = "paused"
    Stopped = "stopped"
    Error = "error"
    Pending = "pending"


def convert_node_status(chain_status: ChainNodeStatus) -> NodeStatus:
    if chain_status == ChainNodeStatus.QUIT:
        return NodeStatus.Stopped
    elif chain_status in [ChainNodeStatus.AVAILABLE, ChainNodeStatus.BUSY]:
        return NodeStatus.Running
    elif chain_status == ChainNodeStatus.PAUSED:
        return NodeStatus.Paused
    elif chain_status in [ChainNodeStatus.PENDING_PAUSE, ChainNodeStatus.PENDING_QUIT]:
        return NodeStatus.Pending
    else:
        raise ValueError(f"unknown ChainNodeStatus: {chain_status}")


class NodeState(BaseModel):
    status: NodeStatus
    message: str = ""
