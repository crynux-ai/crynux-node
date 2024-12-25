from typing import Literal

from pydantic import BaseModel, Field

from .task import TaskType


class ModelConfig(BaseModel):
    id: str
    variant: str | None = None


class DownloadTaskInput(BaseModel):
    task_name: Literal["download"]
    task_type: TaskType
    task_id_commitment: str
    model_type: Literal["base", "lora", "controlnet"]
    model: ModelConfig


class InferenceTaskInput(BaseModel):
    task_name: Literal["inference"]
    task_type: TaskType
    task_id_commitment: str
    model_id: str
    task_args: str
    output_dir: str


class TaskInput(BaseModel):
    task: DownloadTaskInput | InferenceTaskInput = Field(discriminator="task_name")


class SuccessResult(BaseModel):
    status: Literal["success"]


class ErrorResult(BaseModel):
    status: Literal["error"]
    traceback: str


class TaskResult(BaseModel):
    task_name: Literal["inference", "download"]
    task_id_commitment: str
    result: SuccessResult | ErrorResult = Field(discriminator="status")
