from unittest.mock import AsyncMock, MagicMock

from crynux_server.in_memory_model_tracker import (
    InMemoryModelTracker,
    build_in_memory_model,
)
from crynux_server.models import InMemoryModel, ModelFileEntry

HASH = "ab" * 32
FILE = ModelFileEntry(repository="org/m", revision="r1", format="diffusers")


def make_task(**overrides):
    values = dict(
        requested_model_cache_hash=HASH,
        requested_model_cache_config={"dtype": "auto"},
        execution_model_files=[FILE],
    )
    values.update(overrides)
    return MagicMock(**values)


def make_model(hash: str = HASH) -> InMemoryModel:
    return InMemoryModel(
        model_cache_hash=hash,
        model_cache_config={"dtype": "auto"},
        model_files=[FILE],
        execution_dtype="bfloat16",
    )


def make_relay():
    relay = MagicMock()
    relay.node_report_in_memory_model = AsyncMock()
    return relay


def test_build_reports_relay_identity_unchanged():
    model = build_in_memory_model(make_task(), "bfloat16", HASH)
    assert model == make_model()


def test_build_requires_runner_to_echo_requested_hash():
    assert build_in_memory_model(make_task(), "bfloat16", None) is None
    assert build_in_memory_model(make_task(), "bfloat16", "cd" * 32) is None
    assert (
        build_in_memory_model(make_task(requested_model_cache_hash=None), "bfloat16", HASH)
        is None
    )


def test_build_requires_config_files_and_dtype():
    assert (
        build_in_memory_model(
            make_task(requested_model_cache_config=None), "bfloat16", HASH
        )
        is None
    )
    assert (
        build_in_memory_model(make_task(execution_model_files=[]), "bfloat16", HASH)
        is None
    )
    assert build_in_memory_model(make_task(), None, HASH) is None


async def test_sync_reports_initial_empty_state_once():
    tracker = InMemoryModelTracker()
    relay = make_relay()

    await tracker.sync(relay)
    await tracker.sync(relay)

    relay.node_report_in_memory_model.assert_awaited_once_with(None)


async def test_sync_reports_only_changes():
    tracker = InMemoryModelTracker()
    relay = make_relay()
    await tracker.sync(relay)

    model = make_model()
    tracker.set(model, tracker.epoch)
    await tracker.sync(relay)
    await tracker.sync(relay)
    tracker.set(None, tracker.epoch)
    await tracker.sync(relay)

    reported = [c.args[0] for c in relay.node_report_in_memory_model.await_args_list]
    assert reported == [None, model, None]


async def test_reset_reports_empty_and_drops_stale_results():
    tracker = InMemoryModelTracker()
    relay = make_relay()
    epoch = tracker.epoch
    tracker.set(make_model(), epoch)
    await tracker.sync(relay)

    tracker.reset()
    tracker.set(make_model("cd" * 32), epoch)
    await tracker.sync(relay)

    assert tracker.current is None
    reported = [c.args[0] for c in relay.node_report_in_memory_model.await_args_list]
    assert [m.model_cache_hash if m else None for m in reported] == [HASH, None]


async def test_invalidate_forces_next_report():
    tracker = InMemoryModelTracker()
    relay = make_relay()
    await tracker.sync(relay)

    tracker.invalidate()
    await tracker.sync(relay)

    assert relay.node_report_in_memory_model.await_count == 2


async def test_failed_report_is_retried():
    tracker = InMemoryModelTracker()
    relay = make_relay()
    relay.node_report_in_memory_model.side_effect = [RuntimeError("down"), None]

    try:
        await tracker.sync(relay)
    except RuntimeError:
        pass
    await tracker.sync(relay)

    assert relay.node_report_in_memory_model.await_count == 2
