from typing import Optional

from .abc import DownloadTaskStateCache, InferenceTaskStateCache
from .db_impl import DbDownloadTaskStateCache, DbInferenceTaskStateCache
from .memory_impl import (MemoryDownloadTaskStateCache,
                          MemoryInferenceTaskStateCache)

__all__ = [
    "InferenceTaskStateCache",
    "DbInferenceTaskStateCache",
    "DbDownloadTaskStateCache",
    "MemoryInferenceTaskStateCache",
    "MemoryDownloadTaskStateCache",
]


_default_inference_task_state_cache: Optional[InferenceTaskStateCache] = None


def get_inference_task_state_cache() -> InferenceTaskStateCache:
    assert (
        _default_inference_task_state_cache is not None
    ), "InferenceTaskStateCache has not been set."

    return _default_inference_task_state_cache


def set_inference_task_state_cache(cache: InferenceTaskStateCache):
    global _default_inference_task_state_cache

    _default_inference_task_state_cache = cache


_default_download_task_state_cache: Optional[DownloadTaskStateCache] = None


def get_download_task_state_cache() -> DownloadTaskStateCache:
    assert (
        _default_download_task_state_cache is not None
    ), "DownloadTaskStateCache has not been set."

    return _default_download_task_state_cache


def set_download_task_state_cache(cache: DownloadTaskStateCache):
    global _default_download_task_state_cache

    _default_download_task_state_cache = cache
