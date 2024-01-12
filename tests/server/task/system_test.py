import secrets
from typing import Optional

from anyio import Condition, create_task_group, fail_after, sleep
from web3 import Web3

from h_server import models
from h_server.event_queue import EventQueue, MemoryEventQueue
from h_server.task import MemoryTaskStateCache, TaskSystem
from h_server.task.state_cache import TaskStateCache
from h_server.task.task_runner import MockTaskRunner


class AckMemoryEventQueue(MemoryEventQueue):
    def __init__(self, max_size=None) -> None:
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
        distributed=False,
        retry=False
    )

    system.set_runner_cls(MockTaskRunner)

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
        models.TaskSuccess(
            task_id=task_id, result="0x0102030405060708", result_node=address
        ),
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

        with fail_after(5):
            await system.event_queue.put(events[3])
            await queue.wait_ack()

            state = await cache.load(task_id)
            assert state.status == models.TaskStatus.Success

        system.stop()


async def test_task_system_cancel():
    cache = MemoryTaskStateCache()
    queue = AckMemoryEventQueue()

    system = TaskSystem(
        queue=queue,
        state_cache=cache,
        distributed=False,
        retry=False
    )

    system.set_runner_cls(MockTaskRunner)

    task_id = 1
    creator = Web3.to_checksum_address("0xd075aB490857256e6fc85d75d8315e7c9914e008")
    address = Web3.to_checksum_address("0x577887519278199ce8F8D80bAcc70fc32b48daD4")
    task_hash = "0x" + secrets.token_bytes(32).hex()
    data_hash = "0x" + secrets.token_bytes(32).hex()
    round = 1

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
        models.TaskAborted(task_id=task_id),
    ]

    async with create_task_group() as tg:
        tg.start_soon(system.start)

        await system.event_queue.put(events[0])
        with fail_after(5):
            await queue.wait_ack()

        await system.event_queue.put(events[1])
        with fail_after(5):
            await queue.wait_ack()
            state = await cache.load(task_id=task_id)
            assert state.status == models.TaskStatus.Aborted

        system.stop()


async def test_task_system_auto_cancel():
    cache = MemoryTaskStateCache()
    queue = MemoryEventQueue()

    system = TaskSystem(
        queue=queue,
        state_cache=cache,
        distributed=False,
        retry=False
    )

    class TimeoutTaskRunner(MockTaskRunner):
        def __init__(
            self,
            task_id: int,
            task_name: str,
            distributed: bool,
            state_cache: Optional[TaskStateCache] = None,
            queue: Optional[EventQueue] = None,
            timeout: int = 1,
        ):
            super().__init__(
                task_id, task_name, distributed, state_cache, queue, timeout
            )

    system.set_runner_cls(TimeoutTaskRunner)

    task_id = 1
    creator = Web3.to_checksum_address("0xd075aB490857256e6fc85d75d8315e7c9914e008")
    address = Web3.to_checksum_address("0x577887519278199ce8F8D80bAcc70fc32b48daD4")
    task_hash = "0x" + secrets.token_bytes(32).hex()
    data_hash = "0x" + secrets.token_bytes(32).hex()
    round = 1

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
    ]

    async with create_task_group() as tg:
        tg.start_soon(system.start)

        await queue.put(events[0])
        await sleep(1.1)

        state = await cache.load(task_id=task_id)
        assert state.status == models.TaskStatus.Aborted

        system.stop()
