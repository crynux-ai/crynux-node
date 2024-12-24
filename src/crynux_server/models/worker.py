from typing import Literal

from pydantic import BaseModel

from .task import TaskType


class ModelConfig(BaseModel):
    id: str
    variant: str | None = None


class DownloadTaskInput(BaseModel):
    task_type: TaskType
    task_id_commitment: str
    model_type: Literal["base", "vae", "controlnet"]
    model: ModelConfig


class InferenceTaskInput(BaseModel):
    task_type: TaskType
    task_id_commitment: str
    model_id: str
    task_args: str
    output_dir: str


class TaskInput(BaseModel):
    task_name: Literal["inference", "download"]
    task: DownloadTaskInput | InferenceTaskInput
