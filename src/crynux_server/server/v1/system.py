import logging

from anyio import create_task_group, fail_after
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from crynux_server import utils

from ..depends import ConfigDep

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system")


class SystemInfo(BaseModel):
    gpu: utils.GpuInfo
    cpu: utils.CpuInfo
    memory: utils.MemoryInfo
    disk: utils.DiskInfo


@router.get("", response_model=SystemInfo)
async def get_system_info(*, config: ConfigDep):
    info = {}

    try:
        with fail_after(10):
            async with create_task_group() as tg:

                async def _gpu_info():
                    gpu_info = await utils.get_gpu_info()
                    info["gpu"] = gpu_info

                async def _cpu_info():
                    cpu_info = await utils.get_cpu_info()
                    info["cpu"] = cpu_info

                async def _memory_info():
                    memory_info = await utils.get_memory_info()
                    info["memory"] = memory_info

                async def _disk_info():
                    if config.task_config is not None:
                        base_model_dir = config.task_config.hf_cache_dir
                        lora_model_dir = config.task_config.external_cache_dir
                        disk_info = await utils.get_disk_info(
                            base_model_dir,
                            lora_model_dir,
                            config.log.dir,
                        )
                        info["disk"] = disk_info
                    else:
                        info["disk"] = utils.DiskInfo()

                tg.start_soon(_gpu_info)
                tg.start_soon(_cpu_info)
                tg.start_soon(_memory_info)
                tg.start_soon(_disk_info)
    except TimeoutError:
        _logger.error("get system info timeout")
        raise HTTPException(500, "get system info timeout")

    return SystemInfo.model_validate(info)
