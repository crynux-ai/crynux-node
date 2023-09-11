from h_server.models import NodeState, NodeStatus

from .abc import NodeStateCache


class MemoryNodeStateCache(NodeStateCache):
    def __init__(self) -> None:
        self._state = NodeState(status=NodeStatus.Init)

    async def get(self) -> NodeState:
        return self._state

    async def set(self, state: NodeState):
        self._state = state
