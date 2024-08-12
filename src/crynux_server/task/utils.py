import hashlib
import json
import os
import secrets
from typing import List, Tuple

from PIL.Image import Image
from web3 import Web3

import imhash
from crynux_server.models import TaskResultReady, TaskType
from crynux_server.worker_manager import TaskInput, get_worker_manager


def get_image_hash(filename: str) -> str:
    return imhash.getPHash(filename)  # type: ignore


def get_gpt_resp_hash(filename: str) -> str:
    with open(filename, mode="rb") as f:
        return "0x" + hashlib.sha256(f.read()).hexdigest()


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
        task_id=task_id, task_name=task_name, task_type=task_type, task_args=task_args
    )

    task_result = await worker_manager.send_task(task_input)
    results = await task_result.get()
    assert isinstance(results, list)

    files = []
    hashes = []
    checkpoint = ""
    if task_type == TaskType.SD:
        for i, result in enumerate(results):
            assert isinstance(result, Image)
            filename = os.path.join(task_dir, f"{i}.png")
            result.save(filename)
            files.append(filename)
            hashes.append(get_image_hash(filename))
    elif task_type == TaskType.LLM:
        for i, result in enumerate(results):
            filename = os.path.join(task_dir, f"{i}.json")
            with open(filename, mode="w", encoding="utf-8") as f:
                json.dump(result, f)
            files.append(filename)
            hashes.append(get_gpt_resp_hash(filename))
    elif task_type == TaskType.SD_FT:
        assert len(results) == 1
        result_dir = results[0]
        img_dir = os.path.join(result_dir, "validation")
        img_names = sorted(os.listdir(img_dir))
        for img_name in img_names:
            img_file = os.path.join(img_dir, img_name)
            files.append(img_file)
            hashes.append(get_image_hash(img_file))
        checkpoint = os.path.join(result_dir, "checkpoint")

    return TaskResultReady(
        task_id=task_id,
        hashes=hashes,
        files=files,
        checkpoint=checkpoint,
    )
