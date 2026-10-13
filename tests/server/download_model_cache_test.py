import os
import sqlite3

import pytest

from crynux_server import db
from crynux_server.config import DBConfig
from crynux_server.download_model_cache import (
    DbDownloadModelCache,
    MemoryDownloadModelCache,
)
from crynux_server.models import DownloadedModel, ModelFileEntry, TaskType


def make_model(revision: str = "rev-1") -> DownloadedModel:
    return DownloadedModel(
        task_type=TaskType.LLM,
        model_file=ModelFileEntry(
            repository="org/m",
            revision=revision,
            format="gguf",
            format_kwargs={"filename": "m.gguf"},
        ),
    )


async def run_roundtrip(cache):
    first, second = make_model("rev-1"), make_model("rev-2")
    await cache.save(first)
    await cache.save(first)
    await cache.save(second)

    loaded = await cache.load_all()
    assert loaded == [first, second]


async def test_memory_download_model_cache():
    await run_roundtrip(MemoryDownloadModelCache())


async def test_db_download_model_cache(tmp_path):
    filename = str(tmp_path / "test.db")
    await db.init(DBConfig.model_validate({"driver": "sqlite", "filename": filename}))
    try:
        await run_roundtrip(DbDownloadModelCache())
    finally:
        await db.close()
        if os.path.exists(filename):
            os.remove(filename)


def test_download_model_requires_revision():
    with pytest.raises(ValueError):
        make_model("")


async def test_db_init_drops_revisionless_download_tables(tmp_path):
    filename = str(tmp_path / "legacy.db")
    with sqlite3.connect(filename) as conn:
        conn.execute(
            """
            CREATE TABLE download_models (
                id INTEGER PRIMARY KEY,
                task_type VARCHAR(32) NOT NULL,
                model_id VARCHAR NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO download_models VALUES "
            "(1, 'SD', 'base:org/m', '2026-01-01', '2026-01-01')"
        )
        conn.execute(
            """
            CREATE TABLE download_task_states (
                id INTEGER PRIMARY KEY,
                task_id VARCHAR NOT NULL,
                task_type VARCHAR(32) NOT NULL,
                model_id VARCHAR NOT NULL,
                status VARCHAR(32) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )

    await db.init(DBConfig.model_validate({"driver": "sqlite", "filename": filename}))
    try:
        assert await DbDownloadModelCache().load_all() == []
        with sqlite3.connect(filename) as conn:
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(download_models)")
            }
            task_state_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(download_task_states)")
            }
        assert "revision" in columns
        assert "model_files" in task_state_columns
        assert "model_id" not in task_state_columns
    finally:
        await db.close()
