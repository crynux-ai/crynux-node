from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from typing import cast

from h_worker.config import get_config
from h_worker.models import ProxyConfig

from . import utils
from .error import TaskError, TaskInvalid

_logger = logging.getLogger(__name__)


def match_error(stdout: str) -> bool:
    pattern = re.compile(
        r"Task args validation error|Task execution error|Task model not found"
    )
    return pattern.search(stdout) is not None


def inference(
    task_id: int,
    task_type: int,
    task_args: str,
    output_dir: str | None = None,
    hf_cache_dir: str | None = None,
    external_cache_dir: str | None = None,
    script_dir: str | None = None,
    inference_logs_dir: str | None = None,
    result_url: str | None = None,
    distributed: bool = True,
    **kwargs,
):
    assert task_type == 0 or task_type == 1, f"Invalid task type: {task_type}"

    if output_dir is None:
        config = get_config()
        output_dir = config.task.output_dir
    if hf_cache_dir is None:
        config = get_config()
        hf_cache_dir = config.task.hf_cache_dir
    if external_cache_dir is None:
        config = get_config()
        external_cache_dir = config.task.external_cache_dir
    if script_dir is None:
        config = get_config()
        script_dir = config.task.script_dir
    if inference_logs_dir is None:
        config = get_config()
        inference_logs_dir = config.task.inference_logs_dir
    if result_url is None:
        config = get_config()
        result_url = config.task.result_url

    proxy: ProxyConfig | None = None
    if "proxy" in kwargs:
        proxy = kwargs["proxy"]
    else:
        config = get_config()
        if config.task.proxy is not None:
            proxy = cast(ProxyConfig, config.task.proxy.model_dump())

    _logger.info(
        f"task id: {task_id},"
        f"task type: {task_type},"
        f"output_dir: {output_dir},"
        f"task_args: {task_args},"
        f"hf_cache_dir: {hf_cache_dir},"
        f"external_cache_dir: {external_cache_dir},"
        f"script_dir: {script_dir},"
        f"inference_logs_dir: {inference_logs_dir},"
        f"result_url: {result_url},"
    )

    # Check if venv exists. If it exits, use the venv interpreter; else use the current interpreter
    exe = "python"
    worker_venv = os.path.abspath(os.path.join(script_dir, "venv"))
    if os.path.exists(worker_venv):
        exe = os.path.join(worker_venv, "bin", "python")

    result_dir = os.path.abspath(os.path.join(output_dir, str(task_id)))
    if not os.path.exists(result_dir):
        os.makedirs(result_dir, exist_ok=True)

    if not os.path.exists(inference_logs_dir):
        os.makedirs(inference_logs_dir, exist_ok=True)
    log_file = os.path.join(inference_logs_dir, f"{task_id}.log")

    args = [
        exe,
        os.path.abspath(os.path.join(script_dir, "inference.py")),
        str(task_type),
        result_dir,
        f"{task_args}",
    ]

    envs = os.environ.copy()
    envs.update(
        {
            "data_dir__models__huggingface": os.path.abspath(hf_cache_dir),
            "data_dir__models__external": os.path.abspath(external_cache_dir),
        }
    )
    if proxy is not None:
        envs["proxy"] = json.dumps(proxy)

    _logger.info("Start inference task.")
    with open(log_file, mode="w", encoding="utf-8") as f:
        res = subprocess.run(
            args,
            env=envs,
            stdout=f,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        )
    if res.returncode == 0:
        _logger.info("Inference task success.")
    else:
        with open(log_file, mode="r", encoding="utf-8") as f:
            output = f.read()
        if match_error(output):
            raise TaskInvalid
        else:
            raise TaskError

    if distributed:
        result_files = sorted(os.listdir(result_dir))
        result_paths = [os.path.join(result_dir, file) for file in result_files]

        utils.upload_result(result_url + f"/v1/tasks/{task_id}/result", result_paths)
        _logger.info("Upload inference task result.")


def mock_inference(
    task_id: int,
    task_type: int,
    task_args: str,
    output_dir: str | None = None,
    hf_cache_dir: str | None = None,
    external_cache_dir: str | None = None,
    script_dir: str | None = None,
    inference_logs_dir: str | None = None,
    result_url: str | None = None,
    distributed: bool = True,
    **kwargs,
):
    assert task_type == 0 or task_type == 1, f"Invalid task type: {task_type}"

    if output_dir is None:
        config = get_config()
        output_dir = config.task.output_dir
    if hf_cache_dir is None:
        config = get_config()
        hf_cache_dir = config.task.hf_cache_dir
    if external_cache_dir is None:
        config = get_config()
        external_cache_dir = config.task.external_cache_dir
    if script_dir is None:
        config = get_config()
        script_dir = config.task.script_dir
    if inference_logs_dir is None:
        config = get_config()
        inference_logs_dir = config.task.inference_logs_dir
    if result_url is None:
        config = get_config()
        result_url = config.task.result_url

    _logger.info(
        f"task id: {task_id},"
        f"task type: {task_type},"
        f"output_dir: {output_dir},"
        f"task_args: {task_args},"
        f"hf_cache_dir: {hf_cache_dir},"
        f"external_cache_dir: {external_cache_dir},"
        f"script_dir: {script_dir},"
        f"inference_logs_dir: {inference_logs_dir},"
        f"result_url: {result_url},"
    )

    result_dir = os.path.abspath(os.path.join(output_dir, str(task_id)))
    if not os.path.exists(result_dir):
        os.makedirs(result_dir, exist_ok=True)

    if task_type == 0:
        shutil.copyfile("test.png", os.path.join(result_dir, "test.png"))
    elif task_type == 1:
        res = {
            "model": "gpt2",
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {
                        "role": "assistant",
                        "content": '\n\nI have a chat bot, called "Eleanor" which was developed by my team on Skype. '
                        "The only thing I will say is this",
                    },
                    "index": 0,
                }
            ],
            "usage": {"prompt_tokens": 11, "completion_tokens": 30, "total_tokens": 41},
        }
        dst = os.path.join(result_dir, "test.json")
        with open(dst, mode="w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False)

    if distributed:
        utils.upload_result(result_url + f"/v1/tasks/{task_id}/result", ["test.png"])
        _logger.info("Upload inference task result.")
