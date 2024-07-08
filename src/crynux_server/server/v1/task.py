import time
from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from crynux_server.models import NodeStatus, TaskStatus

from ..depends import (ManagerStateCacheDep, TaskStateCacheDep)

router = APIRouter(prefix="/tasks")


class TaskStats(BaseModel):
    status: Literal["running", "idle", "stopped"]
    num_today: int
    num_total: int


@router.get("", response_model=TaskStats)
async def get_task_stats(
    *, task_state_cache: TaskStateCacheDep, state_cache: ManagerStateCacheDep
):
    node_status = (await state_cache.get_node_state()).status
    num_today = 0
    num_total = 0
    if node_status not in [
        NodeStatus.Running,
        NodeStatus.PendingPause,
        NodeStatus.PendingStop,
    ]:
        status = "stopped"
    elif task_state_cache is None:
        status =  "idle"
    else:
        running_status = [
            TaskStatus.Pending,
            TaskStatus.Executing,
            TaskStatus.ResultUploaded,
            TaskStatus.Disclosed,
            TaskStatus.ResultFileUploaded,
        ]
        running_states = await task_state_cache.find(status=running_status)
        if len(running_states) > 0:
            status = "running"
        else:
            status = "idle"
    
    if task_state_cache is not None:
        now = datetime.now().astimezone()
        date = now.date()
        today_ts = time.mktime(date.timetuple())
        today = datetime.fromtimestamp(today_ts)

        today_states = await task_state_cache.find(start=today, status=[TaskStatus.Success])

        total_states = await task_state_cache.find(status=[TaskStatus.Success])

        num_today = len(today_states)
        num_total = len(total_states)

    return TaskStats(
        status=status, num_today=num_today, num_total=num_total
    )
