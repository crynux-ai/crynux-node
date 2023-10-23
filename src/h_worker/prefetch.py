from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import List, TypedDict


_logger = logging.getLogger(__name__)


def call_prefetch_script(
    hf_cache_dir: str,
    external_cache_dir: str,
    script_dir: str,
    base_models: List[ModelConfig] | None = None,
    controlnet_models: List[ModelConfig] | None = None,
    vae_models: List[ModelConfig] | None = None,
    proxy: ProxyConfig | None = None,
):
    exe = "python"
    worker_venv = os.path.abspath(os.path.join(script_dir, "venv"))
    if os.path.exists(worker_venv):
        exe = os.path.join(worker_venv, "bin", "python")

    script_file = os.path.abspath(os.path.join(script_dir, "prefetch.py"))

    args = [exe, script_file]
    envs = os.environ.copy()
    envs["data_dir__models__huggingface"] = os.path.abspath(hf_cache_dir)
    envs["data_dir__models__external"] = os.path.abspath(external_cache_dir)
    if base_models is not None:
        envs["preloaded_models__base"] = json.dumps(base_models)
    if controlnet_models is not None:
        envs["preloaded_models__controlnet"] = json.dumps(controlnet_models)
    if vae_models is not None:
        envs["preloaded_models__vae"] = json.dumps(vae_models)
    if proxy is not None:
        envs["proxy"] = json.dumps(proxy)
    _logger.info("Start prefetching models")
    subprocess.check_call(args, env=envs)
    _logger.info("Prefetching models complete")


class ModelConfig(TypedDict):
    id: str


class ProxyConfig(TypedDict, total=False):
    host: str
    port: int
    username: str
    password: str


def prefetch(
    hf_cache_dir: str,
    external_cache_dir: str,
    script_dir: str,
    base_models: List[ModelConfig] | None = None,
    controlnet_models: List[ModelConfig] | None = None,
    vae_models: List[ModelConfig] | None = None,
    proxy: ProxyConfig | None = None,
):
    if not os.path.exists(hf_cache_dir):
        os.makedirs(hf_cache_dir, exist_ok=True)

    if not os.path.exists(external_cache_dir):
        os.makedirs(external_cache_dir, exist_ok=True)

    try:
        call_prefetch_script(
            hf_cache_dir=hf_cache_dir,
            external_cache_dir=external_cache_dir,
            script_dir=script_dir,
            base_models=base_models,
            controlnet_models=controlnet_models,
            vae_models=vae_models,
            proxy=proxy,
        )
    except Exception as e:
        _logger.exception(e)
        _logger.error("Prefetch error")
        raise
