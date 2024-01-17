from typing import Literal

from fastapi import APIRouter, Body, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing_extensions import Annotated

from h_server import models, utils

from ..depends import NodeStateManagerDep, ManagerStateCacheDep
from .utils import CommonResponse

router = APIRouter(prefix="/node")


class State(BaseModel):
    status: models.NodeStatus
    message: str
    tx_status: models.TxStatus
    tx_error: str

@router.get("", response_model=State)
async def get_node_state(*, state_cache: ManagerStateCacheDep) -> State:
    node_state = await state_cache.get_node_state()
    tx_state = await state_cache.get_tx_state()
    return State(
        status=node_state.status,
        message=node_state.message,
        tx_status=tx_state.status,
        tx_error=tx_state.error
    )


ControlAction = Literal["start", "stop", "pause", "resume"]


class ControlNodeInput(BaseModel):
    action: ControlAction


@router.post("", response_model=CommonResponse)
async def control_node(
    input: Annotated[ControlNodeInput, Body()],
    *,
    state_manager: NodeStateManagerDep,
    background: BackgroundTasks
):
    if state_manager is None:
        raise HTTPException(400, detail="Private key has not been set.")
    if input.action == "start":
        gpu_info = await utils.get_gpu_info()
        wait = await state_manager.start(
            gpu_name=gpu_info.model,
            gpu_vram=gpu_info.vram_total // 1024
        )
    elif input.action == "pause":
        wait = await state_manager.pause()
    elif input.action == "resume":
        wait = await state_manager.resume()
    else:
        wait = await state_manager.stop()

    background.add_task(wait)

    return CommonResponse()