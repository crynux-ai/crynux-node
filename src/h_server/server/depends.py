from fastapi import Depends
from typing import Optional
from typing_extensions import Annotated

from h_server.config import Config, get_config
from h_server.contracts import Contracts, get_contracts
from h_server.node_manager import NodeManager, get_node_manager
from h_server.task import (
    TaskStateCache,
    TaskSystem,
    get_task_state_cache,
    get_task_system,
)


__all__ = [
    "ConfigDep",
    "TaskSystemDep",
    "TaskStateCacheDep",
    "NodeManagerDep",
    "ContractsDep",
]


async def _get_config():
    return get_config()


async def _get_task_system():
    try:
        return get_task_system()
    except AssertionError as e:
        if "TaskSystem has not been set" in str(e):
            return None
        raise


async def _get_task_state_cache():
    return get_task_state_cache()


async def _get_node_manager():
    return get_node_manager()


async def _get_contracts():
    try:
        return get_contracts()
    except AssertionError as e:
        if "Contracts has not been set" in str(e):
            return None
        raise

ConfigDep = Annotated[Config, Depends(_get_config)]
TaskSystemDep = Annotated[Optional[TaskSystem], Depends(_get_task_system)]
TaskStateCacheDep = Annotated[TaskStateCache, Depends(_get_task_state_cache)]
NodeManagerDep = Annotated[NodeManager, Depends(_get_node_manager)]
ContractsDep = Annotated[Optional[Contracts], Depends(_get_contracts)]
