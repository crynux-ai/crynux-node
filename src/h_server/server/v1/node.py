from typing import Literal

from fastapi import APIRouter, Body, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing_extensions import Annotated

from h_server import models
from h_server.node_manager import start, stop, resume, pause

from ..depends import NodeStateManagerDep, ContractsDep
from .utils import CommonResponse

router = APIRouter(prefix="/node")


class State(BaseModel):
    status: models.NodeStatus
    message: str
    tx_status: models.TxStatus
    tx_error: str

@router.get("", response_model=State)
async def get_node_state(*, state_manager: NodeStateManagerDep) -> State:
    node_state = await state_manager.get_node_state()
    tx_state = await state_manager.get_tx_state()
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
    contracts: ContractsDep,
    background: BackgroundTasks
):
    if contracts is None:
        raise HTTPException(400, detail="Private key has not been set.")
    if input.action == "start":
        wait = await start(state_manager=state_manager, contracts=contracts)
    elif input.action == "pause":
        wait = await pause(state_manager=state_manager, contracts=contracts)
    elif input.action == "resume":
        wait = await resume(state_manager=state_manager, contracts=contracts)
    else:
        wait = await stop(state_manager=state_manager, contracts=contracts)

    background.add_task(wait)

    return CommonResponse()