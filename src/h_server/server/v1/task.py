import os
import shutil
from string import hexdigits
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile
from fastapi.concurrency import run_in_threadpool
from typing_extensions import Annotated

from h_server.config import Config, get_config
from h_server.task import get_task_system, TaskSystem
from h_server.models import TaskResultReady

from .utils import CommonResponse

router = APIRouter()


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
    config: Annotated[Config, Depends(get_config)],
    task_system: Annotated[TaskSystem, Depends(get_task_system)],
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
