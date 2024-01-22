from typing import Optional

from .block_cache import BlockNumberCache, DbBlockNumberCache, MemoryBlockNumberCache
from .watcher import EventWatcher

__all__ = [
    "EventWatcher",
    "BlockNumberCache",
    "DbBlockNumberCache",
    "MemoryBlockNumberCache",
    "get_watcher",
    "set_watcher",
]


_default_watcher: Optional[EventWatcher] = None


def get_watcher() -> EventWatcher:
    assert _default_watcher is not None, "EventWatcher has not been set."

    return _default_watcher


def set_watcher(watcher: EventWatcher):
    global _default_watcher

    _default_watcher = watcher
