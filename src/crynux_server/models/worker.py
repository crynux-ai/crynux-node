from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .task import TaskType
from .download_model import ModelConfig
from .model_file import ModelFileEntry


class DownloadTaskInput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    task_name: Literal["download"]
    task_type: TaskType
    task_id: str
    # Task-scoped auxiliary downloads carry `model`; model file downloads carry
    # `model_files`.
    model: Optional[ModelConfig] = None
    model_files: List[ModelFileEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_one_target(self) -> "DownloadTaskInput":
        if (self.model is None) == (len(self.model_files) == 0):
            raise ValueError(
                "A download task requires exactly one of model and model_files"
            )
        return self


class InferenceTaskInput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    task_name: Literal["inference"]
    task_type: TaskType
    task_id: str
    models: List[ModelConfig]
    task_args: str
    output_dir: str
    # Exact model files frozen by the Relay for this execution
    execution_model_files: List[ModelFileEntry] = Field(default_factory=list)
    # Relay-assigned identity of the model the task requests in memory
    requested_model_cache_hash: Optional[str] = None


class TaskInput(BaseModel):
    task: DownloadTaskInput | InferenceTaskInput = Field(discriminator="task_name")


class SuccessResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: Literal["success"]
    execution_dtype: Optional[str] = None
    # Download results list the exact entry of every downloaded model file
    model_files: List[ModelFileEntry] = Field(default_factory=list)
    # Inference results return the requested model cache hash as the identity
    # of the model now held in memory
    model_cache_hash: Optional[str] = None


class ErrorResult(BaseModel):
    status: Literal["error"]
    traceback: str
    # GPUs actually used for this failed task. Absent/0 means the Worker did
    # not report an executed count (legacy workers or no-result cancellations).
    gpu_count: int = 0


class TaskResult(BaseModel):
    task_name: Literal["inference", "download"]
    task_id_commitment: str
    result: SuccessResult | ErrorResult = Field(discriminator="status")
