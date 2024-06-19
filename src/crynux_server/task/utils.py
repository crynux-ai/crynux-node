import json
import os
import secrets
from typing import List, Tuple

from PIL.Image import Image
from crynux_server.models import TaskType, TaskResultReady
from crynux_server.worker_manager import get_worker_manager, TaskInput
from crynux_worker.task.utils import get_gpt_resp_hash, get_image_hash

from web3 import Web3


def make_result_commitments(result_hashes: List[str]) -> Tuple[bytes, bytes, bytes]:
    result_bytes = [bytes.fromhex(h[2:]) for h in result_hashes]
    bs = b"".join(result_bytes)
    nonce = secrets.token_bytes(32)
    commitment = Web3.solidity_keccak(["bytes", "bytes32"], [bs, nonce])
    return bs, commitment, nonce


async def run_task(
    task_name: str,
    task_id: int,
    task_type: TaskType,
    task_args: str,
    task_dir: str,
):
    worker_manager = get_worker_manager()
    task_input = TaskInput(
        task_id=task_id,
        task_name=task_name,
        task_type=task_type,
        task_args=task_args
    )

    task_result = await worker_manager.send_task(task_input)
    results = await task_result.get()
    assert isinstance(results, list)

    files = []
    hashes = []
    for i, result in enumerate(results):
        if task_type == TaskType.SD:
            assert isinstance(result, Image)
            filename = os.path.join(task_dir, f"{i}.png")
            result.save(filename)
            files.append(filename)
            hashes.append(get_image_hash(filename))
        elif task_type == TaskType.LLM:
            filename = os.path.join(task_dir, f"{i}.json")
            with open(filename, mode="w", encoding="utf-8") as f:
                json.dump(result, f)
            files.append(filename)
            hashes.append(get_gpt_resp_hash(filename))
    
    return TaskResultReady(
        task_id=task_id,
        hashes=hashes,
        files=files,
    )
