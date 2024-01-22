import pytest

from crynux_server import db, models
from crynux_server.node_manager.state_cache import (
    MemoryNodeStateCache,
    DbNodeStateCache,
    MemoryTxStateCache,
    DbTxStateCache,
)
from crynux_server.node_manager import ManagerStateCache


@pytest.fixture
async def init_db():
    await db.init("sqlite+aiosqlite://")
    yield
    await db.close()


async def test_node_state_cache(init_db):
    for cls in [MemoryNodeStateCache, DbNodeStateCache]:
        cache = cls()
        assert (await cache.get()).status == models.NodeStatus.Init

        for status in [
            models.NodeStatus.Running,
            models.NodeStatus.Stopped,
            models.NodeStatus.Paused,
            models.NodeStatus.PendingPause,
            models.NodeStatus.PendingStop,
            models.NodeStatus.Error,
        ]:
            msg = ""
            if status == models.NodeStatus.Error:
                msg = "error"

            state = models.NodeState(status=status, message=msg)

            await cache.set(state=state)
            _state = await cache.get()
            assert state.status == _state.status
            assert state.message == _state.message


async def test_tx_state_cache(init_db):
    for cls in [MemoryTxStateCache, DbTxStateCache]:
        cache = cls()

        assert (await cache.get()).status == models.TxStatus.Success
        for status in [
            models.TxStatus.Pending,
            models.TxStatus.Error,
            models.TxStatus.Success,
        ]:
            msg = ""
            if status == models.TxStatus.Error:
                msg = "error"

            state = models.TxState(status=status, error=msg)

            await cache.set(state=state)
            _state = await cache.get()
            assert state.status == _state.status
            assert state.error == _state.error


async def test_manager_state_cache(init_db):
    state_cache = ManagerStateCache()

    assert (await state_cache.get_node_state()).status == models.NodeStatus.Init
    assert (await state_cache.get_tx_state()).status == models.TxStatus.Success

    for status in [
        models.NodeStatus.Running,
        models.NodeStatus.Stopped,
        models.NodeStatus.Paused,
        models.NodeStatus.PendingPause,
        models.NodeStatus.PendingStop,
        models.NodeStatus.Error,
    ]:
        msg = ""
        if status == models.NodeStatus.Error:
            msg = "error"

        await state_cache.set_node_state(status=status, message=msg)
        _state = await state_cache.get_node_state()
        assert _state.status == status
        assert _state.message == msg

    for status in [
        models.TxStatus.Pending,
        models.TxStatus.Error,
        models.TxStatus.Success,
    ]:
        msg = ""
        if status == models.TxStatus.Error:
            msg = "error"

        await state_cache.set_tx_state(status=status, error=msg)
        _state = await state_cache.get_tx_state()
        assert _state.status == status
        assert _state.error == msg
