import os
import secrets
from typing import List, Tuple

from celery.result import AsyncResult
from crynux_server.models import TaskType, TaskResultReady
from crynux_server.config import TaskConfig

from web3 import Web3


def make_result_commitments(result_hashes: List[str]) -> Tuple[bytes, bytes, bytes]:
    result_bytes = [bytes.fromhex(h[2:]) for h in result_hashes]
    bs = b"".join(result_bytes)
    nonce = secrets.token_bytes(32)
    commitment = Web3.solidity_keccak(["bytes", "bytes32"], [bs, nonce])
    return bs, commitment, nonce


def run_distributed_task(
    task_name: str,
    task_id: int,
    task_type: TaskType,
    task_args: str,
):
    from crynux_server.celery_app import get_celery

    celery = get_celery()
    kwargs = {
        "task_id": task_id,
        "task_type": int(task_type),
        "task_args": task_args,
        "distributed": True,
    }
    res: AsyncResult = celery.send_task(
        task_name,
        kwargs=kwargs,
    )
    res.get()


def run_local_task(
    task_name: str,
    task_id: int,
    task_type: TaskType,
    task_args: str,
    task_config: TaskConfig
):
    import crynux_worker.task as h_task
    from crynux_worker.task.utils import (get_gpt_resp_hash,
                                            get_image_hash)

    proxy = None
    if task_config.proxy is not None:
        proxy = task_config.proxy.model_dump()

    task_func = getattr(h_task, task_name)
    kwargs = dict(
        task_id=task_id,
        task_type=int(task_type),
        task_args=task_args,
        distributed=False,
        result_url="",
        output_dir=task_config.output_dir,
        hf_cache_dir=task_config.hf_cache_dir,
        external_cache_dir=task_config.external_cache_dir,
        script_dir=task_config.script_dir,
        inference_logs_dir=task_config.inference_logs_dir,
        proxy=proxy,
    )

    task_func(**kwargs)

    result_dir = os.path.join(
        task_config.output_dir, str(task_id)
    )
    result_files = sorted(os.listdir(result_dir))
    result_paths = [os.path.join(result_dir, file) for file in result_files]
    if task_type == TaskType.SD:
        hashes = [get_image_hash(path) for path in result_paths]
    else:
        hashes = [get_gpt_resp_hash(path) for path in result_paths]
    return TaskResultReady(
        task_id=task_id,
        hashes=hashes,
        files=result_paths,
    )
