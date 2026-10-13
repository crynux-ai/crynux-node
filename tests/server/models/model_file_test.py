import json

import pytest

from crynux_server.models import (
    DownloadModel,
    ModelFileEntry,
    RelayTask,
    TaskType,
    load_event,
    model_files_digest,
    resolve_model_files,
)
from crynux_server.models.download_model import ModelConfig


def entry(repository: str, revision: str = "", **kwargs) -> ModelFileEntry:
    return ModelFileEntry(repository=repository, revision=revision, **kwargs)


def test_entry_defaults_and_null_format_kwargs():
    e = ModelFileEntry.model_validate(
        {"repository": "org/m", "format_kwargs": None}
    )
    assert e.source_type == "huggingface"
    assert e.format_kwargs == {}
    assert not e.is_exact
    assert entry("org/m", "rev").is_exact


def test_entry_digest_ignores_key_order_and_depends_on_revision():
    a = entry("org/m", "r1", format_kwargs={"x": 1, "y": 2})
    b = entry("org/m", "r1", format_kwargs={"y": 2, "x": 1})
    assert a.digest() == b.digest()
    assert a.digest() != entry("org/m", "r2", format_kwargs={"x": 1, "y": 2}).digest()
    assert a.source_key() == entry("org/m", "r2", format_kwargs={"x": 1, "y": 2}).source_key()


def test_model_files_digest_is_order_independent():
    a, b = entry("org/a", "1"), entry("org/b")
    assert model_files_digest([a, b]) == model_files_digest([b, a])
    assert model_files_digest([a]) != model_files_digest([a, b])


def test_resolve_model_files_keeps_exact_and_resolves_source():
    exact = entry("org/a", "1")
    source = entry("org/b", format="diffusers")
    downloaded = [entry("org/b", "9", format="diffusers"), entry("org/c", "3")]

    resolved = resolve_model_files([exact, source], downloaded)

    assert resolved == [exact, entry("org/b", "9", format="diffusers")]


def test_resolve_model_files_requires_downloaded_revision():
    with pytest.raises(ValueError):
        resolve_model_files([entry("org/b")], [entry("org/b")])
    with pytest.raises(ValueError):
        resolve_model_files([entry("org/b", format="gguf")], [entry("org/b", "1")])


def test_model_config_base_entry_has_no_revision():
    sd = ModelConfig(type="base", id="org/sdxl").to_model_file_entry(TaskType.SD)
    llm = ModelConfig(type="base", id="org/llm").to_model_file_entry(TaskType.LLM)

    assert sd == entry("org/sdxl", format="diffusers")
    assert llm == entry("org/llm", format="")


def test_download_model_event_carries_model_files():
    args = json.dumps(
        {
            "node_address": "0x0000000000000000000000000000000000000001",
            "model_files": [
                {
                    "source_type": "huggingface",
                    "repository": "org/m",
                    "revision": "",
                    "format": "diffusers",
                    "format_kwargs": {},
                }
            ],
            "task_type": 0,
        }
    )
    event = load_event(1, "DownloadModel", args)
    assert isinstance(event, DownloadModel)
    assert event.model_files == [entry("org/m", format="diffusers")]


def test_relay_task_accepts_null_execution_model_files():
    data = {
        "sequence": 1,
        "task_args": "{}",
        "task_id_commitment": "0x" + "00" * 32,
        "creator": "0x0000000000000000000000000000000000000001",
        "sampling_seed": "0x" + "00" * 32,
        "nonce": "0x" + "00" * 32,
        "status": 1,
        "task_type": 1,
        "task_version": "3.7.0",
        "timeout": 300,
        "min_vram": 0,
        "required_gpu": "",
        "required_gpu_vram": 0,
        "task_fee": "0",
        "task_size": 1,
        "model_ids": [],
        "score": "0x",
        "qos_score": 0,
        "selected_node": "0x0000000000000000000000000000000000000002",
        "create_time": "2026-01-01T00:00:00Z",
        "start_time": "2026-01-01T00:00:00Z",
        "execution_model_files": None,
    }
    task = RelayTask.model_validate(data)
    assert task.execution_model_files == []
    data["execution_model_files"] = [
        {"repository": "org/m", "revision": "r", "format": "", "format_kwargs": None}
    ]
    task = RelayTask.model_validate(data)
    assert task.execution_model_files == [entry("org/m", "r")]
