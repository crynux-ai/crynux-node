from typing import Optional, Type

from crynux_server import models

from .abc import StateCache
from .db_impl import DbNodeStateCache, DbTxStateCache
from .memory_impl import MemoryNodeStateCache, MemoryTxStateCache

__all__ = [
    "StateCache",
    "DbNodeStateCache",
    "MemoryNodeStateCache",
    "DbTxStateCache",
    "MemoryTxStateCache",
    "ManagerStateCache",
    "get_manager_state_cache",
    "set_manager_state_cache",
]


class ManagerStateCache(object):
    def __init__(
        self,
        node_state_cache_cls: Type[StateCache[models.NodeState]] = DbNodeStateCache,
        tx_state_cache_cls: Type[StateCache[models.TxState]] = DbTxStateCache,
    ) -> None:
        self.node_state_cache = node_state_cache_cls()
        self.tx_state_cache = tx_state_cache_cls()

    async def get_node_state(self) -> models.NodeState:
        return await self.node_state_cache.get()

    async def get_tx_state(self) -> models.TxState:
        return await self.tx_state_cache.get()

    async def set_node_state(self, status: models.NodeStatus, message: str = "", init_message: str = ""):
        return await self.node_state_cache.set(
            models.NodeState(status=status, message=message, init_message=init_message)
        )

    async def set_tx_state(self, status: models.TxStatus, error: str = ""):
        return await self.tx_state_cache.set(models.TxState(status=status, error=error))


_default_state_cache: Optional[ManagerStateCache] = None


def get_manager_state_cache() -> ManagerStateCache:
    assert _default_state_cache is not None, "ManagerStateCache has not been set."

    return _default_state_cache


def set_manager_state_cache(manager: ManagerStateCache):
    global _default_state_cache

    _default_state_cache = manager
