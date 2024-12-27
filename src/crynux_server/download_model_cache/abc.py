from abc import ABC, abstractmethod
from typing import List

from crynux_server.models import DownloadModel


class DownloadModelCache(ABC):
    @abstractmethod
    async def save(self, model: DownloadModel): ...

    @abstractmethod
    async def load_all(self) -> List[DownloadModel]: ...
