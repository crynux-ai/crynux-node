from typing import Optional

from fastapi import Depends
from typing_extensions import Annotated

from crynux_server.config import Config, get_config
from crynux_server.contracts import Contracts, get_contracts
from crynux_server.node_manager import (
    ManagerStateCache,
    NodeStateManager,
    get_manager_state_cache,
    get_node_state_manager,
)
from crynux_server.task import InferenceTaskStateCache, get_inference_task_state_cache
from crynux_server.worker_manager import WorkerManager, get_worker_manager

from .system import get_system_info, SystemInfo
from .account import get_account_info, AccountInfo

__all__ = [
    "ConfigDep",
    "NodeStateManagerDep",
    "TaskStateCacheDep",
    "WorkerManagerDep",
    "SystemInfoDep",
]


async def _get_config():
    return get_config()


async def _get_manager_state_cache():
    return get_manager_state_cache()


async def _get_node_state_manager():
    try:
        return get_node_state_manager()
    except AssertionError as e:
        if "NodeStateManager has not been set" in str(e):
            return None
        raise


async def _get_task_state_cache():
    try:
        return get_inference_task_state_cache()
    except AssertionError as e:
        if "TaskStateCache has not been set" in str(e):
            return None
        raise


async def _get_worker_manager():
    return get_worker_manager()


async def _get_system_info():
    return get_system_info()


async def _get_account_info():
    return get_account_info()


ConfigDep = Annotated[Config, Depends(_get_config)]
ManagerStateCacheDep = Annotated[ManagerStateCache, Depends(_get_manager_state_cache)]
NodeStateManagerDep = Annotated[
    Optional[NodeStateManager], Depends(_get_node_state_manager)
]
TaskStateCacheDep = Annotated[
    Optional[InferenceTaskStateCache], Depends(_get_task_state_cache)
]
WorkerManagerDep = Annotated[WorkerManager, Depends(_get_worker_manager)]
SystemInfoDep = Annotated[SystemInfo, Depends(_get_system_info)]
AccountInfoDep = Annotated[AccountInfo, Depends(_get_account_info)]
