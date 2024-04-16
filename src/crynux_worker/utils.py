import os
import sys
import platform
import logging

from typing import List

_logger = logging.getLogger(__name__)


def _osx_bundle_exe_head(job: str) -> List[str]:
    exe = os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.dirname(sys.executable)),
            "Resources",
            "crynux_worker_process"))
    _logger.debug("Execute Crynux worker from: ", exe)
    return [exe, job]


def _windows_bundle_exe_head(job: str) -> List[str]:
    exe = os.path.abspath(os.path.join(os.path.dirname(sys.executable), "crynux_worker_process", "crynux_worker_process.exe"))
    _logger.debug("Execute Crynux worker from: ", exe)
    return [exe, job]


def _script_cmd_head(job: str, script_dir: str="") -> List[str]:
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


def get_exe_head(job: str, script_dir: str="") -> List[str]:
    if getattr(sys, "frozen", False):
        system_name = platform.system()
        if system_name == "Darwin":
            return _osx_bundle_exe_head(job)
        elif system_name == "Windows":
            return _windows_bundle_exe_head(job)
        else:
            error = RuntimeError(f"Unsupported platform: {system_name}")
            _logger.error(error)
            raise error

    else:
        return _script_cmd_head(job, script_dir)
