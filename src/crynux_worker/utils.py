import os
import sys

from typing import List

def _osx_bundle_exe_head(job: str) -> List[str]:
    exe = os.path.abspath(os.path.join(os.path.dirname(sys.executable), "worker_proc_main"))
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

    script_file = os.path.abspath(os.path.join(script_dir, f"worker_proc_main.py"))
    return [exe, script_file, job]


def get_exe_head(job: str, script_dir: str="") -> List[str]:
    if getattr(sys, "frozen", False):
        return _osx_bundle_exe_head(job)
    else:
        return _script_cmd_head(job, script_dir)


