from abc import ABC, abstractmethod
from typing import List

from crynux_server.models import DownloadedModel


class DownloadModelCache(ABC):
    @abstractmethod
    async def save(self, model: DownloadedModel): ...

    @abstractmethod
    async def load_all(self) -> List[DownloadedModel]: ...
