import logging
import os
import subprocess

_logger = logging.getLogger(__name__)


def call_prefetch_script(hf_cache_dir: str, external_cache_dir: str, script_dir: str):
    exe = "python"
    worker_venv = os.path.abspath(os.path.join(script_dir, "venv"))
    if os.path.exists(worker_venv):
        exe = os.path.join(worker_venv, "bin", "python")

    script_file = os.path.abspath(os.path.join(script_dir, "prefetch.py"))

    args = [exe, script_file]
    envs = os.environ.copy()
    envs["data_dir__models__huggingface"] = os.path.abspath(hf_cache_dir)
    envs["data_dir__models__external"] = os.path.abspath(external_cache_dir)
    _logger.info("Start prefetching models")
    subprocess.check_call(args, env=envs)
    _logger.info("Prefetching models complete")


def prefetch(hf_cache_dir: str, external_cache_dir: str, script_dir: str):
    if not os.path.exists(hf_cache_dir):
        os.makedirs(hf_cache_dir, exist_ok=True)

    if not os.path.exists(external_cache_dir):
        os.makedirs(external_cache_dir, exist_ok=True)

    try:
        call_prefetch_script(hf_cache_dir, external_cache_dir, script_dir)
    except Exception as e:
        _logger.exception(e)
        _logger.error("Prefetch error")
        raise
