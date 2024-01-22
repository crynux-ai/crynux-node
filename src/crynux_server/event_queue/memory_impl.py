from collections import deque
from typing import Tuple, Optional

from anyio import Condition

from crynux_server.models import TaskEvent

from .abc import EventQueue


class MemoryEventQueue(EventQueue):
    def __init__(self, max_size: Optional[int] = None) -> None:
        self.condition = Condition()
        self.queue = deque(maxlen=max_size)

        self._ack_id = 0
        self._no_ack_events = {}

    async def put(self, event: TaskEvent):
        async with self.condition:
            self.queue.append(event)
            self.condition.notify()

    async def get(self) -> Tuple[int, TaskEvent]:
        async with self.condition:
            while len(self.queue) == 0:
                await self.condition.wait()

            event = self.queue.popleft()

        self._ack_id += 1
        self._no_ack_events[self._ack_id] = event
        return self._ack_id, event

    async def ack(self, ack_id: int):
        assert ack_id in self._no_ack_events

        del self._no_ack_events[ack_id]

    async def no_ack(self, ack_id: int):
        assert ack_id in self._no_ack_events

        event = self._no_ack_events.pop(ack_id)
        await self.put(event)
