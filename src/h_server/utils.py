import json
import re
from collections import OrderedDict
from typing import Any, Dict, Optional

from anyio import run_process, Path
from pydantic import BaseModel
from web3 import Web3

from h_server.models.task import PoseConfig, TaskConfig

__all__ = [
    "sort_dict",
    "get_task_hash",
    "get_task_data_hash",
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


def get_task_hash(task: TaskConfig):
    input = task.model_dump()
    ordered_input = sort_dict(input)
    input_bytes = json.dumps(
        ordered_input, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")

    res = Web3.keccak(input_bytes)
    return res.hex()


def get_task_data_hash(base_model: str, lora_model: str, prompt: str, pose: PoseConfig):
    input = {
        "base_model": base_model,
        "lora_model": lora_model,
        "prompt": prompt,
        "pose": pose.model_dump(),
    }
    ordered_input = sort_dict(input)
    input_bytes = json.dumps(
        ordered_input, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")

    res = Web3.keccak(input_bytes)
    return res.hex()


class GpuInfo(BaseModel):
    usage: int = 0
    model: str = ""
    vram_used: int = 0
    vram_total: int = 0


async def get_gpu_info() -> GpuInfo:
    res = await run_process(["nvidia-smi"])
    output = res.stdout.decode()

    info = GpuInfo()
    m = re.search(r"(\d+)MiB\s+/\s+(\d+)MiB", output)
    if m is not None:
        info.vram_used = int(m.group(1))
        info.vram_total = int(m.group(2))
    nums = re.findall(r"(\d+)%", output)
    if len(nums) >= 2:
        info.usage = int(nums[1])

    m = re.search(r"\|\s+\d+\s+(.+?)\s+(On|Off)\s+\|", output)
    if m is not None:
        info.model = m.group(1)
    return info


class CpuInfo(BaseModel):
    usage: int = 0
    num_cores: int = 0
    frequency: int = 0


async def get_cpu_info() -> CpuInfo:
    info = CpuInfo()
    usage_cmd = "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage}'"
    res = await run_process(usage_cmd)
    output = res.stdout.decode()

    info.usage = round(float(output))

    res = await run_process(["cat", "/proc/cpuinfo"])
    output = res.stdout.decode()

    m = re.search(r"cpu\s+MHz\s+:\s+(\d+\.?\d+?)\s+", output)
    if m is not None:
        info.frequency = round(float(m.group(1)))

    ids = re.findall(r"processor\s+:\s+(\d+)\s+", output)
    info.num_cores = len(ids)
    return info


class MemoryInfo(BaseModel):
    available: int = 0
    total: int = 0


async def get_memory_info() -> MemoryInfo:
    info = MemoryInfo()

    res = await run_process(["cat", "/proc/meminfo"])
    output = res.stdout.decode()

    m = re.search(r"MemAvailable:\s+(\d+)", output)
    if m is not None:
        info.available = round(int(m.group(1)) / 1024)

    m = re.search(r"MemTotal:\s+(\d+)", output)
    if m is not None:
        info.total = round(int(m.group(1)) / 1024)

    return info


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
