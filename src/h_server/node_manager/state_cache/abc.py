from abc import ABC, abstractmethod

from h_server.models import NodeState


class NodeStateCache(ABC):
    @abstractmethod
    async def get(self) -> NodeState:
        ...

    @abstractmethod
    async def set(self, state: NodeState):
        ...
