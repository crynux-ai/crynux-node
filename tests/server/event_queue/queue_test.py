import secrets

import pytest
from web3 import Web3

from crynux_server import db, models
from crynux_server.event_queue import DbEventQueue, MemoryEventQueue


async def test_memory_event_queue():
    task_id = 1
    creator = Web3.to_checksum_address("0xd075aB490857256e6fc85d75d8315e7c9914e008")
    address = Web3.to_checksum_address("0x577887519278199ce8F8D80bAcc70fc32b48daD4")
    task_hash = "0x" + secrets.token_bytes(32).hex()
    data_hash = "0x" + secrets.token_bytes(32).hex()
    round = 1

    hashes = ["0x0102030405060708"]
    files = ["test.png"]

    events = [
        models.TaskCreated(
            task_id=task_id,
            task_type=models.TaskType.SD,
            creator=creator,
            selected_node=address,
            task_hash=task_hash,
            data_hash=data_hash,
            round=round,
        ),
        models.TaskResultReady(task_id=task_id, hashes=hashes, files=files),
        models.TaskResultCommitmentsReady(task_id=task_id),
        models.TaskAborted(task_id=task_id),
    ]

    queue = MemoryEventQueue()
    for event in events:
        await queue.put(event)

    for i in range(len(events)):
        ack_id, event = await queue.get()
        assert event == events[i]
        await queue.ack(ack_id)

    await queue.put(events[0])

    ack_id, event = await queue.get()
    assert event == events[0]
    await queue.no_ack(ack_id)

    ack_id, event = await queue.get()
    assert event == events[0]
    await queue.ack(ack_id)


@pytest.fixture(scope="module")
async def init_db():
    await db.init("sqlite+aiosqlite://")
    yield
    await db.close()


async def test_db_event_queue(init_db):
    task_id = 1
    creator = Web3.to_checksum_address("0xd075aB490857256e6fc85d75d8315e7c9914e008")
    address = Web3.to_checksum_address("0x577887519278199ce8F8D80bAcc70fc32b48daD4")
    task_hash = "0x" + secrets.token_bytes(32).hex()
    data_hash = "0x" + secrets.token_bytes(32).hex()
    round = 1

    hashes = ["0x0102030405060708"]
    files = ["test.png"]

    events = [
        models.TaskCreated(
            task_id=task_id,
            task_type=models.TaskType.SD,
            creator=creator,
            selected_node=address,
            task_hash=task_hash,
            data_hash=data_hash,
            round=round,
        ),
        models.TaskResultReady(task_id=task_id, hashes=hashes, files=files),
        models.TaskResultCommitmentsReady(task_id=task_id),
        models.TaskAborted(task_id=task_id),
    ]

    queue = DbEventQueue()
    for event in events:
        await queue.put(event)

    for i in range(len(events)):
        ack_id, event = await queue.get()
        assert event == events[i]
        await queue.ack(ack_id)

    await queue.put(events[0])

    ack_id, event = await queue.get()
    assert event == events[0]
    await queue.no_ack(ack_id)

    ack_id, event = await queue.get()
    assert event == events[0]
    await queue.ack(ack_id)
