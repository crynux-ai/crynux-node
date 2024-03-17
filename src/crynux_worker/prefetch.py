from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import List

from crynux_worker import config, utils
from crynux_worker.config import ModelConfig, ProxyConfig


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
    _logger.info(f"Start worker process: {script_dir}, {hf_cache_dir}, {external_cache_dir}")

    args = utils.get_exe_head("prefetch", script_dir)
    envs = config.set_env(
        hf_cache_dir,
        external_cache_dir,
        base_models,
        controlnet_models,
        vae_models,
        proxy,
    )
    _logger.info("Start prefetching models")
    subprocess.check_call(args, env=envs)
    _logger.info("Prefetching models complete")


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
