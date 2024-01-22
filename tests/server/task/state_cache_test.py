import pytest

from datetime import datetime

from crynux_server import db
from crynux_server.models import TaskState, TaskStatus
from crynux_server.task.state_cache import DbTaskStateCache, MemoryTaskStateCache


async def test_memory_state_cache():
    cache = MemoryTaskStateCache()

    state = TaskState(
        task_id=1,
        round=1,
        status=TaskStatus.Pending,
        files=["test.png"],
        result=bytes.fromhex("01020405060708"),
        timeout=900
    )

    start = datetime.now()
    await cache.dump(state)

    _state = await cache.load(state.task_id)

    assert state == _state

    assert await cache.has(state.task_id)

    assert len(await cache.find()) == 1
    assert len(await cache.find(start=start, end=datetime.now())) == 1
    assert len(await cache.find(start=datetime.now())) == 0
    assert len(await cache.find(start=start, end=datetime.now(), status=[TaskStatus.Pending])) == 1
    assert len(await cache.find(start=start, end=datetime.now(), status=[TaskStatus.Success])) == 0

    state.status = TaskStatus.Success
    await cache.dump(state)
    assert len(await cache.find()) == 1
    assert len(await cache.find(start=start, end=datetime.now())) == 1
    assert len(await cache.find(start=datetime.now())) == 0
    assert len(await cache.find(start=start, end=datetime.now(), status=[TaskStatus.Pending])) == 0
    assert len(await cache.find(start=start, end=datetime.now(), status=[TaskStatus.Success])) == 1


@pytest.fixture
async def init_db():
    await db.init("sqlite+aiosqlite://")
    yield
    await db.close()


async def test_db_state_cache(init_db):
    cache = DbTaskStateCache()

    state = TaskState(
        task_id=1,
        round=1,
        status=TaskStatus.Pending,
        files=["test.png"],
        result=bytes.fromhex("01020405060708"),
        timeout=900,
    )
    
    start = datetime.now()
    await cache.dump(state)

    _state = await cache.load(state.task_id)

    assert state == _state

    assert await cache.has(state.task_id)
    assert len(await cache.find()) == 1
    assert len(await cache.find(start=start, end=datetime.now())) == 1
    assert len(await cache.find(start=datetime.now())) == 0
    assert len(await cache.find(start=start, end=datetime.now(), status=[TaskStatus.Pending])) == 1
    assert len(await cache.find(start=start, end=datetime.now(), status=[TaskStatus.Success])) == 0

    state.status = TaskStatus.Success
    await cache.dump(state)
    assert len(await cache.find()) == 1
    assert len(await cache.find(start=start, end=datetime.now())) == 1
    assert len(await cache.find(start=datetime.now())) == 0
    assert len(await cache.find(start=start, end=datetime.now(), status=[TaskStatus.Pending])) == 0
    assert len(await cache.find(start=start, end=datetime.now(), status=[TaskStatus.Success])) == 1
