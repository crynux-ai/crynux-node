from enum import IntEnum

from pydantic import BaseModel

class ChainEventType(IntEnum):
    TaskStarted = 0
    DownloadModel = 1
    TaskScoreReady = 2
    TaskErrorReported = 3
    TaskValidated = 4
    TaskEndInvalidated = 5
    TaskEndGroupRefund = 6
    TaskEndAborted = 7
    TaskEndSuccess = 8
    TaskEndGroupSuccess = 9
    NodeKickedOut = 10
    NodeSlashed = 11

def show_event_type(event_type: ChainEventType) -> str:
    match event_type:
        case ChainEventType.TaskStarted:
            return "TaskStarted"
        case ChainEventType.DownloadModel:
            return "DownloadModel"
        case ChainEventType.TaskScoreReady:
            return "TaskScoreReady"
        case ChainEventType.TaskErrorReported:
            return "TaskErrorReported"
        case ChainEventType.TaskValidated:
            return "TaskValidated"
        case ChainEventType.TaskEndInvalidated:
            return "TaskEndInvalidated"
        case ChainEventType.TaskEndGroupRefund:
            return "TaskEndGroupRefund"
        case ChainEventType.TaskEndAborted:
            return "TaskEndAborted"
        case ChainEventType.TaskEndSuccess:
            return "TaskEndSuccess"
        case ChainEventType.TaskEndGroupSuccess:
            return "TaskEndGroupSuccess"
        case ChainEventType.NodeKickedOut:
            return "NodeKickedOut"
        case ChainEventType.NodeSlashed:
            return "NodeSlashed"
        case _:
            return "Unknown"

class ChainEvent(BaseModel):
    event_type: ChainEventType
    node_address: str
    task_id_commitment: str
    args: str