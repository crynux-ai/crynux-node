from typing import Optional

from .abc import NodeStateCache
from .db_impl import DbNodeStateCache
from .memory_impl import MemoryNodeStateCache

__all__ = ["NodeStateCache", "DbNodeStateCache", "MemoryNodeStateCache"]


_default_node_state_cache: Optional[NodeStateCache] = None


def get_node_state_cache():
    assert _default_node_state_cache is not None, "NodeStateCache has not been set."

    return _default_node_state_cache


def set_node_state_cache(cache: NodeStateCache):
    global _default_node_state_cache

    _default_node_state_cache = cache
