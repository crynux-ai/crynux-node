import hashlib
import json
from typing import Annotated, Any, Dict, Iterable, List

from pydantic import BaseModel, BeforeValidator, Field, field_validator

SOURCE_TYPE_HUGGINGFACE = "huggingface"
IMAGE_BASE_MODEL_FORMAT = "diffusers"


class ModelFileEntry(BaseModel):
    """One independently downloadable model source.

    An entry with a revision identifies exact files. An entry with an empty
    revision is a source of which one revision is downloaded."""

    source_type: str = SOURCE_TYPE_HUGGINGFACE
    repository: str
    revision: str = ""
    format: str = ""
    format_kwargs: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("format_kwargs", mode="before")
    @classmethod
    def _null_format_kwargs(cls, v: Any) -> Any:
        return {} if v is None else v

    @property
    def is_exact(self) -> bool:
        return self.revision != ""

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def source_key(self) -> str:
        return self.model_copy(update={"revision": ""}).canonical_json()


def _null_to_empty_list(v: Any) -> Any:
    return [] if v is None else v


# Relay encodes an empty entry list as JSON null
ModelFileList = Annotated[List[ModelFileEntry], BeforeValidator(_null_to_empty_list)]


def model_files_digest(model_files: Iterable[ModelFileEntry]) -> str:
    """Order-independent digest of a model file requirement list."""
    canonical = sorted(entry.canonical_json() for entry in model_files)
    return hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest()


def resolve_model_files(
    requirements: List[ModelFileEntry], downloaded: List[ModelFileEntry]
) -> List[ModelFileEntry]:
    """Return the exact entry of every requirement.

    An exact requirement resolves to itself. A source requirement resolves to
    the downloaded entry of the same source that carries a revision."""
    downloaded_by_source: Dict[str, ModelFileEntry] = {
        entry.source_key(): entry for entry in downloaded if entry.is_exact
    }
    resolved: List[ModelFileEntry] = []
    for requirement in requirements:
        if requirement.is_exact:
            resolved.append(requirement)
            continue
        entry = downloaded_by_source.get(requirement.source_key())
        if entry is None:
            raise ValueError(
                f"Download result has no revision for model file {requirement.repository}"
            )
        resolved.append(entry)
    return resolved
