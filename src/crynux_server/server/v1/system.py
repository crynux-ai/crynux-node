from fastapi import APIRouter

from ..depends import SystemInfoDep
from ..system import SystemInfo

router = APIRouter(prefix="/system")


@router.get("", response_model=SystemInfo)
async def get_system_info(*, system_info: SystemInfoDep):
    return system_info
