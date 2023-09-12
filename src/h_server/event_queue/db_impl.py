import logging
from collections import deque
from typing import Optional, Tuple

import sqlalchemy as sa
from anyio import Condition, Lock

from h_server import db
from h_server.db import models as db_models
from h_server.models import TaskEvent, load_event_from_json

from .abc import EventQueue


_logger = logging.getLogger()


class DbEventQueue(EventQueue):
    def __init__(self, max_size: Optional[int] = None) -> None:
        self.queue = deque(maxlen=max_size)
        self.lock = Lock()
        self.condition = Condition(self.lock)
        self.synced = False

        self._no_ack_events = {}

    async def _sync_from_db(self):
        if not self.synced:
            async with self.lock:
                async with db.session_scope() as sess:
                    offset = 0
                    limit = 30
                    while True:
                        q = (
                            sa.select(db_models.TaskEvent)
                            .order_by(db_models.TaskEvent.id)
                            .limit(limit)
                            .offset(offset)
                        )
                        event_models = (await sess.scalars(q)).all()
                        if len(event_models) == 0:
                            break
                        for event_model in event_models:
                            event = load_event_from_json(event_model.kind, event_model.event)
                            self.queue.append((event_model.id, event))
                        offset += limit
                self.synced = True

    async def _put(self, id: int, event: TaskEvent):
        async with self.condition:
            self.queue.append((id, event))
            self.condition.notify()

    async def _get(self) -> Tuple[int, TaskEvent]:
        async with self.condition:
            while len(self.queue) == 0:
                await self.condition.wait()
            id, event = self.queue.popleft()
            return id, event

    async def put(self, event: TaskEvent):
        await self._sync_from_db()

        async with db.session_scope() as sess:
            event_str = event.model_dump_json()
            event_model = db_models.TaskEvent(kind=event.kind, event=event_str)
            sess.add(event_model)
            await sess.commit()
            await sess.refresh(event_model)
            model_id = event_model.id

        await self._put(model_id, event)
        _logger.debug(f"put event {event} to queue")

    async def get(self) -> Tuple[int, TaskEvent]:
        await self._sync_from_db()

        ack_id, event = await self._get()

        self._no_ack_events[ack_id] = event

        _logger.debug(f"get {ack_id} event {event}")
        return ack_id, event

    async def ack(self, ack_id: int):
        if ack_id not in self._no_ack_events:
            raise KeyError(f"Event ack id {ack_id} not found.")

        async with db.session_scope() as sess:
            q = sa.select(db_models.TaskEvent).where(db_models.TaskEvent.id == ack_id)

            event_model = (await sess.scalars(q)).one()
            await sess.delete(event_model)
            await sess.commit()

        event = self._no_ack_events.pop(ack_id)
        _logger.debug(f"ack {ack_id} event {event}")

    async def no_ack(self, ack_id: int):
        if ack_id not in self._no_ack_events:
            raise KeyError(f"Event ack id {ack_id} not found.")

        event = self._no_ack_events.pop(ack_id)
        await self._put(ack_id, event)
        _logger.debug(f"no ack {ack_id} event {event}")
