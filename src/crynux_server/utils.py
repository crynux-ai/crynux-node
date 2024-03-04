import json
import re
from collections import OrderedDict
import platform
from typing import Any, Dict, Optional

from anyio import run_process, Path
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


async def get_linux_memory_info() -> MemoryInfo:
    info = MemoryInfo()

    res = await run_process(["cat", "/proc/meminfo"])
    output = res.stdout.decode()

    m = re.search(r"MemAvailable:\s+(\d+)", output)
    if m is not None:
        info.available_mb = round(int(m.group(1)) / 1024)

    m = re.search(r"MemTotal:\s+(\d+)", output)
    if m is not None:
        info.total_mb = round(int(m.group(1)) / 1024)

    return info

async def get_osx_memory_info() -> MemoryInfo:
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
    memory_info_fn = {
        "Darwin": get_osx_memory_info,
        "Linux": get_linux_memory_info,
    }
    return await memory_info_fn[get_os()]()


class GpuInfo(BaseModel):
    usage: int = 0
    model: str = ""
    vram_used_mb: int = 0
    vram_total_mb: int = 0


async def get_linux_gpu_info() -> GpuInfo:
    res = await run_process(["nvidia-smi"])
    output = res.stdout.decode()

    info = GpuInfo()
    m = re.search(r"(\d+)MiB\s+/\s+(\d+)MiB", output)
    if m is not None:
        info.vram_used_mb = int(m.group(1))
        info.vram_total_mb = int(m.group(2))
    nums = re.findall(r"(\d+)%", output)
    if len(nums) >= 2:
        info.usage = int(nums[1])

    m = re.search(r"\|\s+\d+\s+(.+?)\s+(On|Off)\s+\|", output)
    if m is not None:
        info.model = m.group(1)
    return info


async def get_osx_gpu_info() -> GpuInfo:

    mem_info = await get_osx_memory_info()
    info = GpuInfo(
        vram_used_mb=mem_info.total_mb - mem_info.available_mb,
        vram_total_mb=mem_info.total_mb
    )

    res = await run_process("system_profiler SPDisplaysDataType")
    output = res.stdout.decode()
    m = re.search(r"Chipset Model:([\w\s]+)", output)
    if m is not None:
        info.model = m.group(1)
    return info


async def get_gpu_info() -> GpuInfo:
    gpu_info_fn = {
        "Darwin": get_osx_gpu_info,
        "Linux": get_linux_gpu_info,
    }
    return await gpu_info_fn[get_os()]()


class CpuInfo(BaseModel):
    usage: int = 0
    num_cores: int = 0
    frequency_mhz: int = 0
    description: str = ""


async def get_linux_cpu_info() -> CpuInfo:
    info = CpuInfo()
    usage_cmd = "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage}'"
    res = await run_process(usage_cmd)
    output = res.stdout.decode()

    info.usage = round(float(output))

    res = await run_process(["cat", "/proc/cpuinfo"])
    output = res.stdout.decode()

    m = re.search(r"cpu\s+MHz\s+:\s+(\d+\.?\d+?)\s+", output)
    if m is not None:
        info.frequency_mhz = round(float(m.group(1)))

    ids = re.findall(r"processor\s+:\s+(\d+)\s+", output)
    info.num_cores = len(ids)
    return info


async def get_osx_cpu_info() -> CpuInfo:
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
    cpu_info_fn = {
        "Darwin": get_osx_cpu_info,
        "Linux": get_linux_cpu_info,
    }
    return await cpu_info_fn[get_os()]()



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
    if await Path(base_model_dir).exists():
        res = await run_process(["du", "-s", base_model_dir])
        output = res.stdout.decode()
        m = re.search(r"(\d+)", output)
        if m is not None:
            info.base_models = round(int(m.group(1)) / (1024 ** 2))

    if await Path(lora_model_dir).exists():
        res = await run_process(["du", "-s", lora_model_dir])
        output = res.stdout.decode()
        m = re.search(r"(\d+)", output)
        if m is not None:
            info.lora_models = round(int(m.group(1)) / 1024)

    if await Path(log_dir).exists():
        res = await run_process(["du", "-s", log_dir])
        output = res.stdout.decode()
        m = re.search(r"(\d+)", output)
        if m is not None:
            info.logs += int(m.group(1))

    if inference_log_dir is not None and await Path(inference_log_dir).exists():
        res = await run_process(["du", "-s", inference_log_dir])
        output = res.stdout.decode()
        m = re.search(r"(\d+)", output)
        if m is not None:
            info.logs += int(m.group(1))

    return info
