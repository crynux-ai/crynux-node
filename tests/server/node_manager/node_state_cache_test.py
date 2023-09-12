import pytest

from h_server import db, models
from h_server.node_manager.state_cache import MemoryNodeStateCache, DbNodeStateCache


async def test_memory_node_state_cache():
    cache = MemoryNodeStateCache()
    assert (await cache.get()).status == models.NodeStatus.Init

    for status in [
        models.NodeStatus.Running,
        models.NodeStatus.Stopped,
        models.NodeStatus.Paused,
        models.NodeStatus.Pending,
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


@pytest.fixture(scope="module")
async def init_db():
    await db.init("sqlite+aiosqlite://")
    yield
    await db.close()


async def test_db_node_state_cache(init_db):
    cache = DbNodeStateCache()
    assert (await cache.get()).status == models.NodeStatus.Init

    for status in [
        models.NodeStatus.Running,
        models.NodeStatus.Stopped,
        models.NodeStatus.Paused,
        models.NodeStatus.Pending,
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


