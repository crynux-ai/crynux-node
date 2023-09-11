import os

from anyio import create_task_group, to_thread
from fastapi import APIRouter
from pydantic import BaseModel
from typing_extensions import Annotated

from h_server import utils

from ..depends import ConfigDep

router = APIRouter(prefix="/system")


class SystemInfo(BaseModel):
    gpu: utils.GpuInfo
    cpu: utils.CpuInfo
    memory: utils.MemoryInfo
    disk: utils.DiskInfo


@router.get("", response_model=SystemInfo)
async def get_system_info(*, config: ConfigDep):
    info = {}

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
                base_model_dir = config.task_config.pretrained_models_dir
                lora_model_dir = os.path.join(config.task_config.data_dir, "model")
                log_dir = os.path.join(config.task_config.inference_logs_dir)
                disk_info = await to_thread.run_sync(
                    utils.get_disk_info, base_model_dir, lora_model_dir, log_dir
                )
                info["disk"] = disk_info
            else:
                info["disk"] = utils.DiskInfo()

        tg.start_soon(_gpu_info)
        tg.start_soon(_cpu_info)
        tg.start_soon(_memory_info)
        tg.start_soon(_disk_info)

    return SystemInfo.model_validate(info)
