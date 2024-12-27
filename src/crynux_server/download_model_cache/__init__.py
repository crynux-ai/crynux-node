from typing import Optional

from .abc import DownloadModelCache
from .db_impl import DbDownloadModelCache
from .memory_impl import MemoryDownloadModelCache

__all__ = [
    "DownloadModelCache",
    "DbDownloadModelCache",
    "MemoryDownloadModelCache",
    "get_download_model_cache",
    "set_download_model_cache",
]

_default_download_model_cache: Optional[DownloadModelCache] = None


def get_download_model_cache() -> DownloadModelCache:
    assert _default_download_model_cache is not None

    return _default_download_model_cache


def set_download_model_cache(cache: DownloadModelCache):
    global _default_download_model_cache

    _default_download_model_cache = cache
