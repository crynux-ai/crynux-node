from typing import Any, List

from pydantic import BaseModel, ConfigDict

from .model_file import ModelFileEntry


class InMemoryModel(BaseModel):
    """The model the inference worker currently holds in memory."""

    model_config = ConfigDict(protected_namespaces=())

    model_cache_hash: str
    model_cache_config: Any
    model_files: List[ModelFileEntry]
    execution_dtype: str
