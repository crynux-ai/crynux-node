from typing import Literal

from fastapi import APIRouter, Body
from pydantic import BaseModel
from typing_extensions import Annotated

from h_server.models import NodeState

from ..depends import NodeManagerDep
from .utils import CommonResponse

router = APIRouter(prefix="/node")


@router.get("", response_model=NodeState)
async def get_node_state(*, node_manager: NodeManagerDep) -> NodeState:
    return await node_manager.get_state()


ControlAction = Literal["start", "stop", "pause", "resume"]


class ControlNodeInput(BaseModel):
    action: ControlAction


@router.post("", response_model=CommonResponse)
async def control_node(
    input: Annotated[ControlNodeInput, Body()],
    *,
    node_manager: NodeManagerDep,
):
    if input.action == "start":
        await node_manager.start()
    elif input.action == "pause":
        await node_manager.pause()
    elif input.action == "resume":
        await node_manager.resume()
    elif input.action == "stop":
        await node_manager.stop()

    return CommonResponse()