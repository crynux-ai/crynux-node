from typing import Optional

from fastapi import Depends
from typing_extensions import Annotated

from h_server.config import Config, get_config
from h_server.contracts import Contracts, get_contracts
from h_server.event_queue import EventQueue, get_event_queue
from h_server.node_manager import NodeManager, get_node_manager
from h_server.task import TaskStateCache, get_task_state_cache

__all__ = [
    "ConfigDep",
    "TaskStateCacheDep",
    "NodeManagerDep",
    "ContractsDep",
    "EventQueueDep",
]


async def _get_config():
    return get_config()


async def _get_node_manager():
    return get_node_manager()


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
NodeManagerDep = Annotated[NodeManager, Depends(_get_node_manager)]
EventQueueDep = Annotated[Optional[EventQueue], Depends(_get_event_queue)]
TaskStateCacheDep = Annotated[Optional[TaskStateCache], Depends(_get_task_state_cache)]
ContractsDep = Annotated[Optional[Contracts], Depends(_get_contracts)]
