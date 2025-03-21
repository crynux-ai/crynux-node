from typing import Literal

from pydantic import BaseModel, Field

from .common import AddressFromStr, BytesFromHex
from .task import InferenceTaskStatus, TaskAbortReason, TaskError, TaskType

EventType = Literal[
    "TaskStarted",
    "DownloadModel",
    "TaskScoreReady",
    "TaskErrorReported",
    "TaskValidated",
    "TaskEndInvalidated",
    "TaskEndGroupRefund",
    "TaskEndAborted",
    "TaskEndSuccess",
    "TaskEndGroupSuccess",
    "NodeKickedOut",
    "NodeSlashed",
]


class Event(BaseModel):
    type: EventType = Field(init_var=False)


class TaskStarted(Event):
    type: EventType = Field(default="TaskStarted", init_var=False, frozen=True)
    selected_node: AddressFromStr
    task_id_commitment: BytesFromHex


class DownloadModel(Event):
    type: EventType = Field(default="DownloadModel", init_var=False, frozen=True)
    node_address: AddressFromStr
    model_id: str
    task_type: TaskType


class TaskScoreReady(Event):
    type: EventType = Field(default="TaskScoreReady", init_var=False, frozen=True)
    task_id_commitment: BytesFromHex
    selected_node: AddressFromStr
    score: BytesFromHex


class TaskErrorReported(Event):
    type: EventType = Field(default="TaskErrorReported", init_var=False, frozen=True)
    task_id_commitment: BytesFromHex
    selected_node: AddressFromStr
    task_error: TaskError


class TaskValidated(Event):
    type: EventType = Field(default="TaskValidated", init_var=False, frozen=True)
    task_id_commitment: BytesFromHex
    selected_node: AddressFromStr


class TaskEndInvalidated(Event):
    type: EventType = Field(default="TaskEndInvalidated", init_var=False, frozen=True)
    task_id_commitment: BytesFromHex
    selected_node: AddressFromStr


class TaskEndGroupRefund(Event):
    type: EventType = Field(default="TaskEndGroupRefund", init_var=False, frozen=True)
    task_id_commitment: BytesFromHex
    selected_node: AddressFromStr


class TaskEndAborted(Event):
    type: EventType = Field(default="TaskEndAborted", init_var=False, frozen=True)
    task_id_commitment: BytesFromHex
    abort_issuer: AddressFromStr
    last_status: InferenceTaskStatus
    abort_reason: TaskAbortReason


class TaskEndSuccess(Event):
    type: EventType = Field(default="TaskEndSuccess", init_var=False, frozen=True)
    task_id_commitment: BytesFromHex
    selected_node: AddressFromStr


class TaskEndGroupSuccess(Event):
    type: EventType = Field(default="TaskEndGroupSuccess", init_var=False, frozen=True)
    task_id_commitment: BytesFromHex
    selected_node: AddressFromStr


class NodeKickedOut(Event):
    type: EventType = Field(default="NodeKickedOut", init_var=False, frozen=True)
    node_address: AddressFromStr


class NodeSlashed(Event):
    type: EventType = Field(default="NodeSlashed", init_var=False, frozen=True)
    node_address: AddressFromStr


def load_event_from_json(type: EventType, event_json: str) -> Event:
    try:
        cls = globals()[type]
        assert issubclass(cls, Event)
        return cls.model_validate_json(event_json)
    except (KeyError, AssertionError):
        raise ValueError(f"unknown event type {type} from json")
