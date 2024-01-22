from typing import Optional

from .abc import TaskStateCache
from .db_impl import DbTaskStateCache
from .memory_impl import MemoryTaskStateCache

__all__ = ["TaskStateCache", "DbTaskStateCache", "MemoryTaskStateCache"]


_default_task_state_cache: Optional[TaskStateCache] = None


def get_task_state_cache() -> TaskStateCache:
    assert _default_task_state_cache is not None, "TaskStateCache has not been set."

    return _default_task_state_cache


def set_task_state_cache(cache: TaskStateCache):
    global _default_task_state_cache

    _default_task_state_cache = cache
