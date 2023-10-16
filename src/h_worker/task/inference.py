from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess

from h_worker.config import get_config

from . import utils
from .error import TaskError, TaskInvalid

_logger = logging.getLogger(__name__)


def match_error(stdout: str) -> bool:
    pattern = re.compile(
        r"Task args validation error|Task execution error|Task model not found"
    )
    return pattern.search(stdout) is not None


def sd_lora_inference(
    task_id: int,
    task_args: str,
    output_dir: str | None = None,
    hf_cache_dir: str | None = None,
    external_cache_dir: str | None = None,
    script_dir: str | None = None,
    result_url: str | None = None,
    distributed: bool = True,
):
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
    if result_url is None:
        config = get_config()
        result_url = config.task.result_url

    _logger.info(
        f"task id: {task_id},"
        f"output_dir: {output_dir},"
        f"task_args: {task_args},"
        f"hf_cache_dir: {hf_cache_dir},"
        f"external_cache_dir: {external_cache_dir},"
        f"script_dir: {script_dir}"
    )

    # Check if venv exists. If it exits, use the venv interpreter; else use the current interpreter
    exe = "python"
    worker_venv = os.path.abspath(os.path.join(script_dir, "venv"))
    if os.path.exists(worker_venv):
        exe = os.path.join(worker_venv, "bin", "python")

    image_dir = os.path.abspath(os.path.join(output_dir, str(task_id)))
    if not os.path.exists(image_dir):
        os.makedirs(image_dir, exist_ok=True)

    args = [
        exe,
        os.path.abspath(os.path.join(script_dir, "inference.py")),
        image_dir,
        f"'{task_args}'",
    ]

    envs = os.environ.copy()
    envs.update(
        {
            "data_dir__models__huggingface": os.path.abspath(hf_cache_dir),
            "data_dir__models__external": os.path.abspath(external_cache_dir),
        }
    )

    _logger.info("Start inference task.")
    res = subprocess.run(
        args,
        env=envs,
        capture_output=True,
        encoding="utf-8",
    )
    if res.returncode == 0:
        _logger.info("Inference task success.")
    else:
        if match_error(res.stdout):
            _logger.error(res.stderr)
            raise TaskInvalid
        else:
            raise TaskError

    if distributed:
        image_files = sorted(os.listdir(image_dir))
        image_paths = [os.path.join(image_dir, file) for file in image_files]

        utils.upload_result(result_url + f"/v1/tasks/{task_id}/result", image_paths)
        _logger.info("Upload inference task result.")


def mock_lora_inference(
    task_id: int,
    task_args: str,
    output_dir: str | None = None,
    hf_cache_dir: str | None = None,
    external_cache_dir: str | None = None,
    script_dir: str | None = None,
    result_url: str | None = None,
    distributed: bool = True,
):
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
    if result_url is None:
        config = get_config()
        result_url = config.task.result_url

    _logger.info(
        f"task id: {task_id},"
        f"output_dir: {output_dir},"
        f"task_args: {task_args},"
        f"hf_cache_dir: {hf_cache_dir},"
        f"external_cache_dir: {external_cache_dir},"
        f"script_dir: {script_dir}"
    )

    image_dir = os.path.abspath(os.path.join(output_dir, str(task_id)))
    if not os.path.exists(image_dir):
        os.makedirs(image_dir, exist_ok=True)

    shutil.copyfile("test.png", os.path.join(image_dir, "test.png"))

    if distributed:
        utils.upload_result(result_url + f"/v1/tasks/{task_id}/result", ["test.png"])
        _logger.info("Upload inference task result.")
