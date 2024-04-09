import platform
import re
from collections import OrderedDict
from typing import Any, Dict, Optional

import psutil
from anyio import Path, run_process, to_thread
from pydantic import BaseModel
from web3 import Web3

__all__ = [
    "sort_dict",
    "get_os",
    "get_task_hash",
    "GpuInfo",
    "get_gpu_info",
    "CpuInfo",
    "get_cpu_info",
    "MemoryInfo",
    "get_memory_info",
    "DiskInfo",
    "get_disk_info",
]


def sort_dict(input: Dict[str, Any]) -> Dict[str, Any]:
    keys = sorted(input.keys())

    res = OrderedDict()
    for key in keys:
        value = input[key]
        if isinstance(value, dict):
            value = sort_dict(value)
        res[key] = value

    return res


def get_task_hash(task_args: str):
    res = Web3.keccak(task_args.encode("utf-8"))
    return res.hex()


def get_os():
    return platform.system()


class MemoryInfo(BaseModel):
    available_mb: int = 0
    total_mb: int = 0


async def _get_memory_info() -> MemoryInfo:
    info = MemoryInfo()

    svmem = await to_thread.run_sync(psutil.virtual_memory)

    info.total_mb = svmem.total // (2 ** 20)
    info.available_mb = svmem.available // (2 ** 20)

    return info


async def _get_osx_memory_info() -> MemoryInfo:
    info = MemoryInfo()
    res = await run_process(["sysctl", "hw.memsize"])
    output = res.stdout.decode()
    total_mem = re.match(r"hw.memsize: (\d+)", output)
    if total_mem:
        info.total_mb = round(int(total_mem.group(1)) / 1024 / 1024)

    usage_cmd = ("vm_stat | perl -ne '/page size of (\\d+)/ and $size=$1; "
                 "/Pages\\s+free[^\\d]+(\\d+)/ and printf(\"%.2f\",  $1 * $size / 1048576);'")
    res = await run_process(usage_cmd)
    output = res.stdout.decode()
    info.available_mb = int(float(output))

    return info


async def get_memory_info() -> MemoryInfo:
    if get_os() == "Darwin":
        return await _get_osx_memory_info()
    else:
        return await _get_memory_info()


class GpuInfo(BaseModel):
    usage: int = 0
    model: str = ""
    vram_used_mb: int = 0
    vram_total_mb: int = 0


async def _get_nvidia_gpu_info() -> GpuInfo:
    res = await run_process(
        "nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv"
    )
    output = res.stdout.decode()
    result_line = output.split("\n")[1].strip()
    results = result_line.split(",")
    assert len(results) == 4

    info = GpuInfo()

    p = re.compile(r"(\d+)")

    info.model = results[0].strip()

    m = p.search(results[1])
    if m is not None:
        info.usage = int(m.group(1))
    m = p.search(results[2])
    if m is not None:
        info.vram_used_mb = int(m.group(1))
    m = p.search(results[3])
    if m is not None:
        info.vram_total_mb = int(m.group(1))

    return info


async def _get_osx_gpu_info() -> GpuInfo:
    mem_info = await _get_osx_memory_info()
    info = GpuInfo(
        vram_used_mb=mem_info.total_mb - mem_info.available_mb,
        vram_total_mb=mem_info.total_mb,
    )

    res = await run_process("system_profiler SPDisplaysDataType")
    output = res.stdout.decode()
    m = re.search(r"Chipset Model:([\w\s]+)", output)
    if m is not None:
        info.model = m.group(1)
    return info


async def get_gpu_info() -> GpuInfo:
    if get_os() == "Darwin":
        return await _get_osx_gpu_info()
    else:
        return await _get_nvidia_gpu_info()


class CpuInfo(BaseModel):
    usage: int = 0
    num_cores: int = 0
    frequency_mhz: int = 0
    description: str = ""


async def _get_cpu_info() -> CpuInfo:
    info = CpuInfo()

    info.usage = int(await to_thread.run_sync(psutil.cpu_percent))
    info.num_cores = await to_thread.run_sync(psutil.cpu_count)
    info.frequency_mhz = int((await to_thread.run_sync(psutil.cpu_freq)).max)

    return info


async def _get_osx_cpu_info() -> CpuInfo:
    info = CpuInfo()
    usage_cmd = r"ps -A -o %cpu | awk '{s+=$1} END {print s}'"
    res = await run_process(usage_cmd)
    output = res.stdout.decode()
    info.usage = round(float(output) * 100)

    res = await run_process(["sysctl", "-n", "machdep.cpu.brand_string"])
    output = res.stdout.decode()
    info.description = output

    res = await run_process(["sysctl", "hw.logicalcpu"])
    output = res.stdout.decode()
    ids = re.match(r"hw.logicalcpu: (\d+)", output)
    if ids:
        info.num_cores = int(ids.group(1))
    return info


async def get_cpu_info() -> CpuInfo:
    if get_os() == "Darwin":
        return await _get_osx_cpu_info()
    else:
        return await _get_cpu_info()


class DiskInfo(BaseModel):
    base_models: int = 0
    lora_models: int = 0
    logs: int = 0


async def get_disk_info(
        base_model_dir: str,
        lora_model_dir: str,
        log_dir: str,
        inference_log_dir: Optional[str] = None,
) -> DiskInfo:
    info = DiskInfo()
    path = Path(base_model_dir)
    if await path.exists():
        size = 0
        async for f in path.rglob("*"):
            if await f.is_file():
                size += (await f.stat()).st_size
        info.base_models = size // (2 ** 30)

    path = Path(lora_model_dir)
    if await path.exists():
        size = 0
        async for f in path.rglob("*"):
            if await f.is_file():
                size += (await f.stat()).st_size
        info.lora_models = size // (2 ** 20)

    path = Path(log_dir)
    if await path.exists():
        size = 0
        async for f in path.rglob("*"):
            if await f.is_file():
                size += (await f.stat()).st_size
        info.logs += size // 1024

    if inference_log_dir is not None:
        path = Path(inference_log_dir)
        if await path.exists():
            size = 0
            async for f in path.rglob("*"):
                if await f.is_file():
                    size += (await f.stat()).st_size
            info.logs += size // 1024

    return info
