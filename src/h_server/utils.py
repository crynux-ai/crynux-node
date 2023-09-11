import json
import os
import re
from collections import OrderedDict
from typing import Any, Dict

from pydantic import BaseModel
from web3 import Web3
from anyio import run_process
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


def get_disk_info(base_model_dir: str, lora_model_dir: str, log_dir: str) -> DiskInfo:
    base_models = [
        path
        for path in os.listdir(base_model_dir)
        if os.path.isdir(os.path.join(base_model_dir, path))
    ]
    lora_models = [
        path
        for path in os.listdir(lora_model_dir)
        if os.path.isdir(os.path.join(lora_model_dir, path))
    ]
    log_files = [
        path
        for path in os.listdir(log_dir)
        if os.path.isfile(os.path.join(log_dir, path))
    ]
    return DiskInfo(
        base_models=len(base_models), lora_models=len(lora_models), logs=len(log_files)
    )
