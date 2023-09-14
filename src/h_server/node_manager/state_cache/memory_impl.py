from h_server.models import NodeState, NodeStatus, TxState, TxStatus
from h_server.models.tx import TxState

from .abc import StateCache


class MemoryNodeStateCache(StateCache[NodeState]):
    def __init__(self) -> None:
        self._state = NodeState(status=NodeStatus.Init)

    async def get(self) -> NodeState:
        return self._state

    async def set(self, state: NodeState):
        self._state = state


class MemoryTxStateCache(StateCache[TxState]):
    def __init__(self) -> None:
        self._state = TxState(status=TxStatus.Success)

    async def get(self) -> TxState:
        return self._state

    async def set(self, state: TxState):
        self._state = state
