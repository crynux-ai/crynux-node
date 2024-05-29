from __future__ import annotations

import json
import logging
import os
import platform
import re
import subprocess
import sys
from typing import Callable, Dict, List, Tuple

from crynux_worker.models import ModelConfig, ProxyConfig

_logger = logging.getLogger(__name__)


def _osx_bundle_exe_head(job: str) -> List[str]:
    exe = os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.dirname(sys.executable)),
            "Resources",
            "crynux_worker_process",
        )
    )
    _logger.debug("Execute Crynux worker from: ", exe)
    return [exe, job]


def _windows_bundle_exe_head(job: str) -> List[str]:
    exe = os.path.abspath(
        os.path.join(
            os.path.dirname(sys.executable),
            "crynux_worker_process",
            "crynux_worker_process.exe",
        )
    )
    _logger.debug("Execute Crynux worker from: ", exe)
    return [exe, job]

def _linux_bundle_exe_head(job: str) -> List[str]:
    exe = os.path.abspath(os.path.join(os.path.dirname(sys.executable), "crynux_worker_process", "crynux_worker_process"))
    _logger.debug("Execute Crynux worker from: ", exe)
    return [exe, job]

def _script_cmd_head(job: str, script_dir: str = "") -> List[str]:
    exe = "python"
    worker_venv = os.path.abspath(os.path.join(script_dir, "venv"))
    if os.path.exists(worker_venv):
        # linux
        linux_exe = os.path.join(worker_venv, "bin", "python")
        windows_exe = os.path.join(worker_venv, "Scripts", "python.exe")
        if os.path.exists(linux_exe):
            exe = linux_exe
        elif os.path.exists(windows_exe):
            exe = windows_exe

    script_file = os.path.abspath(os.path.join(script_dir, f"crynux_worker_process.py"))
    return [exe, script_file, job]


def get_exe_head(job: str, script_dir: str = "") -> List[str]:
    if getattr(sys, "frozen", False):
        system_name = platform.system()
        if system_name == "Darwin":
            return _osx_bundle_exe_head(job)
        elif system_name == "Windows":
            return _windows_bundle_exe_head(job)
        elif system_name == "Linux":
            return _linux_bundle_exe_head(job)
        else:
            error = RuntimeError(f"Unsupported platform: {system_name}")
            _logger.error(error)
            raise error

    else:
        return _script_cmd_head(job, script_dir)


def is_task_error(stdout: str) -> bool:
    pattern = re.compile(r"crynux worker process error")
    return pattern.search(stdout) is not None


def run_worker(args: List[str], envs: Dict[str, str], line_callback: Callable[[str], None] | None = None) -> Tuple[bool, str]:
    output = ""
    success = True
    with subprocess.Popen(
        args=args,
        env=envs,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as sp:
        assert sp.stdout is not None
        for line in sp.stdout:
            output += line
            if line_callback is not None:
                line_callback(line)
            if is_task_error(line):
                success = False

    if not success:
        _logger.error(f"crynux worker error \nargs: {args} \nlogs: \n{output}")
    return success, output


def set_env(
    hf_cache_dir: str,
    external_cache_dir: str,
    sd_base_models: List[ModelConfig] | None = None,
    gpt_base_models: List[ModelConfig] | None = None,
    controlnet_models: List[ModelConfig] | None = None,
    vae_models: List[ModelConfig] | None = None,
    proxy: ProxyConfig | None = None
):
    envs = os.environ.copy()
    envs["sd_data_dir__models__huggingface"] = os.path.abspath(hf_cache_dir)
    envs["gpt_data_dir__models__huggingface"] = os.path.abspath(hf_cache_dir)
    envs["sd_data_dir__models__external"] = os.path.abspath(external_cache_dir)
    envs["gpt_data_dir__models__external"] = os.path.abspath(external_cache_dir)
    if sd_base_models is not None:
        envs["sd_preloaded_models__base"] = json.dumps(sd_base_models)
    if gpt_base_models is not None:
        envs["gpt_preloaded_models__base"] = json.dumps(gpt_base_models)
    if controlnet_models is not None:
        envs["sd_preloaded_models__controlnet"] = json.dumps(controlnet_models)
    if vae_models is not None:
        envs["sd_preloaded_models__vae"] = json.dumps(vae_models)
    if proxy is not None:
        envs["sd_proxy"] = json.dumps(proxy)
        envs["gpt_proxy"] = json.dumps(proxy)
    return envs
