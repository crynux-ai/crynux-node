from typing import Dict, List

from crynux_server.models import DownloadedModel

from .abc import DownloadModelCache


class MemoryDownloadModelCache(DownloadModelCache):
    def __init__(self):
        self._download_models: Dict[str, DownloadedModel] = {}

    async def save(self, model: DownloadedModel):
        self._download_models[model.model_file.digest()] = model

    async def load_all(self) -> List[DownloadedModel]:
        return list(self._download_models.values())
