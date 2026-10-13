from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from .model_file import IMAGE_BASE_MODEL_FORMAT, ModelFileEntry
from .model_name import normalize_model_name
from .task import TaskType


class ModelConfig(BaseModel):
    id: str
    type: Literal["base", "lora", "controlnet"]
    variant: str | None = None

    @field_validator("id")
    @classmethod
    def _normalize_id(cls, v: str) -> str:
        return normalize_model_name(v)

    def to_model_id(self) -> str:
        model_body = self.id
        if self.variant:
            model_body += f"+{self.variant}"
        return f"{self.type}:{model_body}"

    @classmethod
    def from_model_id(cls, model_id: str) -> "ModelConfig":
        model_type, model_body = model_id.split(":", maxsplit=1)
        if "+" in model_body:
            model_name, variant = model_body.split("+", maxsplit=1)
        else:
            model_name = model_body
            variant = None
        return cls.model_validate(
            {"id": model_name, "type": model_type, "variant": variant}
        )

    def to_model_file_entry(self, task_type: TaskType) -> ModelFileEntry:
        """Source entry of a base model; the entry carries no revision."""
        if self.type != "base":
            raise ValueError(f"Model type {self.type} has no model file entry")
        model_format = "" if task_type == TaskType.LLM else IMAGE_BASE_MODEL_FORMAT
        return ModelFileEntry(repository=self.id, format=model_format)


class DownloadedModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    task_type: TaskType
    model_file: ModelFileEntry

    @field_validator("model_file")
    @classmethod
    def _require_revision(cls, v: ModelFileEntry) -> ModelFileEntry:
        if not v.is_exact:
            raise ValueError("A downloaded model file requires a revision")
        return v
