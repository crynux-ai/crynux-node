import json
from collections import OrderedDict
from typing import Any, Dict

from web3 import Web3

from h_server.models.task import PoseConfig, TaskConfig


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
