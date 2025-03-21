from hashlib import sha256
from typing import Dict, List

from crynux_server.models import DownloadedModel

from .abc import DownloadModelCache


class MemoryDownloadModelCache(DownloadModelCache):
    def __init__(self):
        self._download_models: Dict[str, DownloadedModel] = {}

    async def save(self, model: DownloadedModel):
        model_id = model.model.to_model_id()
        model_id_hash = sha256(model_id.encode("utf-8")).hexdigest()
        self._download_models[model_id_hash] = model

    async def load_all(self) -> List[DownloadedModel]:
        return list(self._download_models.values())
