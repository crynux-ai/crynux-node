from typing import Optional

from fastapi import Depends
from typing_extensions import Annotated

from crynux_server.config import Config, get_config
from crynux_server.contracts import Contracts, get_contracts
from crynux_server.event_queue import EventQueue, get_event_queue
from crynux_server.node_manager import (
    ManagerStateCache,
    NodeStateManager,
    get_manager_state_cache,
    get_node_state_manager,
)
from crynux_server.task import TaskStateCache, get_task_state_cache

__all__ = [
    "ConfigDep",
    "NodeStateManagerDep",
    "TaskStateCacheDep",
    "ContractsDep",
    "EventQueueDep",
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


async def _get_event_queue():
    try:
        return get_event_queue()
    except AssertionError as e:
        if "Event queue has not been set" in str(e):
            return None
        raise


async def _get_task_state_cache():
    try:
        return get_task_state_cache()
    except AssertionError as e:
        if "TaskStateCache has not been set" in str(e):
            return None
        raise


async def _get_contracts():
    try:
        return get_contracts()
    except AssertionError as e:
        if "Contracts has not been set" in str(e):
            return None
        raise


ConfigDep = Annotated[Config, Depends(_get_config)]
ManagerStateCacheDep = Annotated[ManagerStateCache, Depends(_get_manager_state_cache)]
NodeStateManagerDep = Annotated[Optional[NodeStateManager], Depends(_get_node_state_manager)]
EventQueueDep = Annotated[Optional[EventQueue], Depends(_get_event_queue)]
TaskStateCacheDep = Annotated[Optional[TaskStateCache], Depends(_get_task_state_cache)]
ContractsDep = Annotated[Optional[Contracts], Depends(_get_contracts)]
