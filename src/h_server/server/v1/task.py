import os
import shutil
from datetime import datetime, timedelta
from string import hexdigits
from typing import List, Literal

from fastapi import (APIRouter, File, Form, HTTPException, Path,
                     UploadFile)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing_extensions import Annotated

from h_server.models import TaskResultReady, TaskStatus

from ..depends import ConfigDep, TaskStateCacheDep, TaskSystemDep
from .utils import CommonResponse

router = APIRouter(prefix="/tasks")


def store_result_files(task_dir: str, task_id: str, files: List[UploadFile]):
    result_dir = os.path.join(task_dir, task_id)
    if not os.path.exists(result_dir):
        os.makedirs(result_dir, exist_ok=True)

    dsts: List[str] = []
    for file in files:
        assert file.filename is not None
        dst_filename = os.path.join(result_dir, file.filename)
        with open(dst_filename, mode="wb") as dst:
            shutil.copyfileobj(file.file, dst)
        dsts.append(dst_filename)
    return dsts


def is_valid_hexstr(h: str) -> bool:
    if not h.startswith("0x"):
        return False
    return all(c in hexdigits for c in h[2:])


@router.post("/{task_id}/result", response_model=CommonResponse)
async def upload_result(
    task_id: Annotated[int, Path(description="The task id")],
    hashes: Annotated[List[str], Form(description="The task result file hashes")],
    files: Annotated[List[UploadFile], File(description="The task result files")],
    *,
    config: ConfigDep,
    task_system: TaskSystemDep,
) -> CommonResponse:
    if not (await task_system.has_task(task_id=task_id)):
        raise HTTPException(status_code=400, detail=f"Task {task_id} does not exist.")

    for h in hashes:
        if not is_valid_hexstr(h):
            raise HTTPException(
                status_code=400, detail="Hash is not a valid hex string."
            )

    for file in files:
        if file.filename is None:
            raise HTTPException(status_code=400, detail="Filename is missing.")

    dsts = await run_in_threadpool(
        store_result_files, config.task_dir, str(task_id), files
    )

    event = TaskResultReady(task_id=task_id, hashes=hashes, files=dsts)
    await task_system.event_queue.put(event)

    return CommonResponse()


class TaskStats(BaseModel):
    status: Literal["running", "idle"]
    num_today: int
    num_total: int


@router.get("", response_model=TaskStats)
async def get_task_stats(
    *,
    task_system: TaskSystemDep,
    task_state_cache: TaskStateCacheDep,
):
    if await task_system.is_running():
        status = "running"
    else:
        status = "idle"

    now = datetime.now()
    today_start = now - timedelta(days=1)

    num_today = await task_state_cache.count(
        start=today_start, deleted=True, status=TaskStatus.Success
    )

    num_total = await task_state_cache.count(deleted=True, status=TaskStatus.Success)

    return TaskStats(status=status, num_today=num_today, num_total=num_total)
