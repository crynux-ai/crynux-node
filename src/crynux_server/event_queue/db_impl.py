import logging
from typing import Tuple, Dict

import sqlalchemy as sa
from anyio import Condition

from crynux_server import db
from crynux_server.db import models as db_models
from crynux_server.models import TaskEvent, load_event_from_json

from .abc import EventQueue


_logger = logging.getLogger()


class DbEventQueue(EventQueue):
    def __init__(self) -> None:
        self.condition = Condition()

        self._ack_id = 0
        self._no_ack_events: Dict[int, TaskEvent] = {}

    async def get_count(self) -> int:
        async with db.session_scope() as sess:
            q = sa.select(sa.func.count(db_models.TaskEvent.id))
            count = (await sess.execute(q)).scalar_one()
        return count

    async def put(self, event: TaskEvent):
        async with self.condition:
            async with db.session_scope() as sess:
                event_str = event.model_dump_json()
                event_model = db_models.TaskEvent(kind=event.kind, event=event_str)
                sess.add(event_model)
                await sess.commit()
            self.condition.notify(1)

        _logger.debug(f"put event {event} to queue")

    async def get(self) -> Tuple[int, TaskEvent]:

        async with self.condition:
            while (await self.get_count()) <= 0:
                await self.condition.wait()
    
        async with db.session_scope() as sess:
            q = sa.select(db_models.TaskEvent).order_by(db_models.TaskEvent.id).limit(1)

            event_model = (await sess.scalars(q)).first()
            assert event_model is not None
            await sess.delete(event_model)
            await sess.commit()

        event = load_event_from_json(kind=event_model.kind, event_json=event_model.event)
        self._ack_id += 1
        self._no_ack_events[self._ack_id] = event

        _logger.debug(f"get {self._ack_id} event {event}")
        return self._ack_id, event

    async def ack(self, ack_id: int):
        if ack_id not in self._no_ack_events:
            raise KeyError(f"Event ack id {ack_id} not found.")

        event = self._no_ack_events.pop(ack_id)
        _logger.debug(f"ack {ack_id} event {event}")

    async def no_ack(self, ack_id: int):
        if ack_id not in self._no_ack_events:
            raise KeyError(f"Event ack id {ack_id} not found.")

        event = self._no_ack_events.pop(ack_id)
        await self.put(event)
        _logger.debug(f"no ack {ack_id} event {event}")
