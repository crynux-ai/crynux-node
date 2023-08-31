import secrets

from anyio import Condition, create_task_group, fail_after
from web3 import Web3

from h_server import models
from h_server.contracts import Contracts
from h_server.event_queue import MemoryEventQueue
from h_server.relay import Relay
from h_server.task import MemoryTaskStateCache, TaskSystem
from h_server.task.task_runner import TestTaskRunner


class AckMemoryEventQueue(MemoryEventQueue):
    def __init__(self, max_size = None) -> None:
        super().__init__(max_size)

        self._ack_condition = Condition()
        self._ack_ids = []

    async def ack(self, ack_id: int):
        await super().ack(ack_id)
        async with self._ack_condition:
            self._ack_ids.append(ack_id)
            self._ack_condition.notify()
    
    async def wait_ack(self) -> int:
        async with self._ack_condition:
            while len(self._ack_ids) == 0:
                await self._ack_condition.wait()
            return self._ack_ids.pop(0)


async def test_task_system():
    cache = MemoryTaskStateCache()
    queue = AckMemoryEventQueue()

    system = TaskSystem(
        queue=queue,
        state_cache=cache,
    )

    system.set_runner_cls(TestTaskRunner)

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
            creator=creator,
            selected_node=address,
            task_hash=task_hash,
            data_hash=data_hash,
            round=round,
        ),
        models.TaskResultReady(task_id=task_id, hashes=hashes, files=files),
        models.TaskResultCommitmentsReady(task_id=task_id),
        models.TaskSuccess(task_id=task_id, result="0x0102030405060708", result_node=address)
    ]

    async with create_task_group() as tg:
        tg.start_soon(system.start)

        await system.event_queue.put(events[0])
        with fail_after(5):
            await queue.wait_ack()
            state = await cache.load(task_id)
            assert state.status == models.TaskStatus.Executing

        await system.event_queue.put(events[1])
        with fail_after(5):
            await queue.wait_ack()
            state = await cache.load(task_id)
            assert state.status == models.TaskStatus.ResultUploaded

        await system.event_queue.put(events[2])
        with fail_after(5):
            await queue.wait_ack()
            state = await cache.load(task_id)
            assert state.status == models.TaskStatus.Disclosed

        await system.event_queue.put(events[3])
        await queue.wait_ack()
    
        exist = await system.has_task(task_id)
        assert not exist

        system.stop()

