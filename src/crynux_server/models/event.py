from typing import List, Literal

from eth_typing import ChecksumAddress
from pydantic import BaseModel, Field
from web3 import Web3
from web3.types import EventData

from .task import TaskAbortReason, TaskError, TaskStatus, TaskType

TaskKind = Literal[
    "TaskQueued",
    "TaskStarted",
    "TaskParametersUploaded",
    "TaskErrorReported",
    "TaskScoreReady",
    "TaskValidated",
    "TaskEndSuccess",
    "TaskEndInvalidated",
    "TaskEndAborted",
    "TaskEndGroupSuccess",
    "TaskEndGroupRefund",
]


class TaskEvent(BaseModel):
    kind: TaskKind = Field(init_var=False)
    task_id_commitment: bytes


class TaskQueued(TaskEvent):
    kind: TaskKind = Field(default="TaskQueued", init_var=False, frozen=True)


class TaskStarted(TaskEvent):
    kind: TaskKind = Field(default="TaskStarted", init_var=False, frozen=True)
    selected_node: ChecksumAddress


class TaskParametersUploaded(TaskEvent):
    kind: TaskKind = Field(
        default="TaskParametersUploaded", init_var=False, frozen=True
    )
    selected_node: ChecksumAddress


class TaskErrorReported(TaskEvent):
    kind: TaskKind = Field(default="TaskErrorReported", init_var=False, frozen=True)
    selected_node: ChecksumAddress
    error: TaskError


class TaskScoreReady(TaskEvent):
    kind: TaskKind = Field(default="TaskScoreReady", init_var=False, frozen=True)
    selected_node: ChecksumAddress
    task_score: bytes


class TaskValidated(TaskEvent):
    kind: TaskKind = Field(default="TaskValidated", init_var=False, frozen=True)


class TaskEndSuccess(TaskEvent):
    kind: TaskKind = Field(default="TaskEndSuccess", init_var=False, frozen=True)


class TaskEndInvalidated(TaskEvent):
    kind: TaskKind = Field(default="TaskEndInvalidated", init_var=False, frozen=True)


class TaskEndGroupSuccess(TaskEvent):
    kind: TaskKind = Field(default="TaskEndGroupSuccess", init_var=False, frozen=True)


class TaskEndGroupRefund(TaskEvent):
    kind: TaskKind = Field(default="TaskEndGroupRefund", init_var=False, frozen=True)


class TaskEndAborted(TaskEvent):
    kind: TaskKind = Field(default="TaskEndAborted", init_var=False, frozen=True)
    abort_issuer: ChecksumAddress
    last_status: TaskStatus
    abort_reason: TaskAbortReason


def load_event_from_json(kind: TaskKind, event_json: str) -> TaskEvent:
    try:
        cls = globals()[kind]
        assert isinstance(cls, TaskEvent)
        return cls.model_validate_json(event_json)
    except (KeyError, AssertionError):
        raise ValueError(f"unknown event kind {kind} from json")


def load_event_from_contracts(event_data: EventData) -> TaskEvent:
    name = event_data["event"]
    if name == "TaskQueued":
        return TaskQueued(task_id_commitment=event_data["args"]["taskIDCommitment"])
    elif name == "TaskStarted":
        return TaskStarted(
            task_id_commitment=event_data["args"]["taskIDCommitment"],
            selected_node=Web3.to_checksum_address(event_data["args"]["selectedNode"]),
        )
    elif name == "TaskParametersUploaded":
        return TaskParametersUploaded(
            task_id_commitment=event_data["args"]["taskIDCommitment"],
            selected_node=Web3.to_checksum_address(event_data["args"]["selectedNode"]),
        )
    elif name == "TaskErrorReported":
        return TaskErrorReported(
            task_id_commitment=event_data["args"]["taskIDCommitment"],
            selected_node=Web3.to_checksum_address(event_data["args"]["selectedNode"]),
            error=TaskError(event_data["args"]["error"]),
        )
    elif name == "TaskScoreReady":
        return TaskScoreReady(
            task_id_commitment=event_data["args"]["taskIDCommitment"],
            selected_node=Web3.to_checksum_address(event_data["args"]["selectedNode"]),
            task_score=event_data["args"]["taskScore"],
        )
    elif name == "TaskValidated":
        return TaskValidated(task_id_commitment=event_data["args"]["taskIDCommitment"])
    elif name == "TaskEndSuccess":
        return TaskEndSuccess(task_id_commitment=event_data["args"]["taskIDCommitment"])
    elif name == "TaskEndInvalidated":
        return TaskEndInvalidated(
            task_id_commitment=event_data["args"]["taskIDCommitment"],
        )
    elif name == "TaskEndGroupSuccess":
        return TaskEndGroupSuccess(
            task_id_commitment=event_data["args"]["taskIDCommitment"],
        )
    elif name == "TaskEndGroupRefund":
        return TaskEndGroupRefund(
            task_id_commitment=event_data["args"]["taskIDCommitment"],
        )
    elif name == "TaskEndAborted":
        return TaskEndAborted(
            task_id_commitment=event_data["args"]["taskIDCommitment"],
            abort_issuer=Web3.to_checksum_address(event_data["args"]["abortIssuer"]),
            last_status=TaskStatus(event_data["args"]["lastStatus"]),
            abort_reason=TaskAbortReason(event_data["args"]["abortReason"]),
        )
    else:
        raise ValueError(f"unknown event kind {name} from contracts")
