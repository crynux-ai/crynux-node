from typing import List, Literal

from eth_typing import ChecksumAddress
from pydantic import BaseModel, Field
from web3.types import EventData
from web3 import Web3

from .task import TaskType

TaskKind = Literal[
    "TaskStarted",
    "TaskResultReady",
    "TaskResultCommitmentsReady",
    "TaskSuccess",
    "TaskAborted",
]


class TaskEvent(BaseModel):
    kind: TaskKind = Field(init_var=False)
    task_id: int


class TaskStarted(TaskEvent):
    kind: TaskKind = Field(default="TaskStarted", init_var=False, frozen=True)
    task_type: TaskType
    creator: ChecksumAddress
    selected_node: ChecksumAddress
    task_hash: str
    data_hash: str
    round: int


class TaskResultReady(TaskEvent):
    kind: TaskKind = Field(default="TaskResultReady", init_var=False, frozen=True)
    hashes: List[str]
    files: List[str]


class TaskResultCommitmentsReady(TaskEvent):
    kind: TaskKind = Field(
        default="TaskResultCommitmentsReady", init_var=False, frozen=True
    )


class TaskSuccess(TaskEvent):
    kind: TaskKind = Field(default="TaskSuccess", init_var=False, frozen=True)
    result: str
    result_node: ChecksumAddress


class TaskAborted(TaskEvent):
    kind: TaskKind = Field(default="TaskAborted", init_var=False, frozen=True)


def load_event_from_json(kind: TaskKind, event_json: str) -> TaskEvent:
    if kind == "TaskStarted":
        return TaskStarted.model_validate_json(event_json)
    elif kind == "TaskResultReady":
        return TaskResultReady.model_validate_json(event_json)
    elif kind == "TaskResultCommitmentsReady":
        return TaskResultCommitmentsReady.model_validate_json(event_json)
    elif kind == "TaskSuccess":
        return TaskSuccess.model_validate_json(event_json)
    elif kind == "TaskAborted":
        return TaskAborted.model_validate_json(event_json)
    else:
        raise ValueError(f"unknown event kind {kind} from json")


def load_event_from_contracts(event_data: EventData) -> TaskEvent:
    name = event_data["event"]
    if name == "TaskStarted":
        return TaskStarted(
            task_id=event_data["args"]["taskId"],
            task_type=event_data["args"]["taskType"],
            creator=Web3.to_checksum_address(event_data["args"]["creator"]),
            selected_node=Web3.to_checksum_address(event_data["args"]["selectedNode"]),
            task_hash=Web3.to_hex(event_data["args"]["taskHash"]),
            data_hash=Web3.to_hex(event_data["args"]["dataHash"]),
            round=event_data["args"]["round"],
        )
    elif name == "TaskResultCommitmentsReady":
        return TaskResultCommitmentsReady(task_id=event_data["args"]["taskId"])
    elif name == "TaskSuccess":
        return TaskSuccess(
            task_id=event_data["args"]["taskId"],
            result=Web3.to_hex(event_data["args"]["result"]),
            result_node=Web3.to_checksum_address(event_data["args"]["resultNode"]),
        )
    elif name == "TaskAborted":
        return TaskAborted(task_id=event_data["args"]["taskId"])
    else:
        raise ValueError(f"unknown event kind {name} from contracts")
