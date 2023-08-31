from typing import Optional

from .abc import EventQueue
from .db_impl import DbEventQueue
from .memory_impl import MemoryEventQueue

__all__ = [
    "EventQueue",
    "DbEventQueue",
    "MemoryEventQueue",
    "get_event_queue",
    "set_event_queue",
]


_event_queue: Optional[EventQueue] = None


def get_event_queue():
    assert _event_queue is not None, "Event queue has not been set."

    return _event_queue


def set_event_queue(queue: EventQueue):
    global _event_queue

    _event_queue = queue
