from __future__ import annotations

import logging
import os
import re
from typing import Callable, List

from crynux_worker import config, utils
from crynux_worker.config import ModelConfig, ProxyConfig

_logger = logging.getLogger(__name__)


def call_prefetch_script(
    hf_cache_dir: str,
    external_cache_dir: str,
    script_dir: str,
    sd_base_models: List[ModelConfig] | None = None,
    gpt_base_models: List[ModelConfig] | None = None,
    controlnet_models: List[ModelConfig] | None = None,
    vae_models: List[ModelConfig] | None = None,
    proxy: ProxyConfig | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
):
    _logger.info(
        f"Start worker process: {script_dir}, {hf_cache_dir}, {external_cache_dir}"
    )

    args = utils.get_exe_head("prefetch", script_dir)
    envs = config.set_env(
        hf_cache_dir,
        external_cache_dir,
        sd_base_models,
        gpt_base_models,
        controlnet_models,
        vae_models,
        proxy,
    )
    _logger.info("Start downloading models")

    total_models = 0
    if sd_base_models is not None:
        total_models += len(sd_base_models)
    if gpt_base_models is not None:
        total_models += len(gpt_base_models)
    if controlnet_models is not None:
        total_models += len(controlnet_models)
    if vae_models is not None:
        total_models += len(vae_models)

    current_models = 0
    progress_pattern = re.compile(r"Preloading")

    def line_callback(line: str):
        nonlocal current_models

        if progress_pattern.search(line) is not None:
            current_models += 1
            if progress_callback is not None:
                progress_callback(current_models, total_models)

    success, _ = utils.run_worker(args=args, envs=envs, line_callback=line_callback)
    if not success:
        raise ValueError("Failed to download models due to network issue")
    _logger.info("Downloading models complete")


def prefetch(
    hf_cache_dir: str,
    external_cache_dir: str,
    script_dir: str,
    sd_base_models: List[ModelConfig] | None = None,
    gpt_base_models: List[ModelConfig] | None = None,
    controlnet_models: List[ModelConfig] | None = None,
    vae_models: List[ModelConfig] | None = None,
    proxy: ProxyConfig | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
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
            sd_base_models=sd_base_models,
            gpt_base_models=gpt_base_models,
            controlnet_models=controlnet_models,
            vae_models=vae_models,
            proxy=proxy,
            progress_callback=progress_callback,
        )
    except Exception as e:
        _logger.exception(e)
        _logger.error("Error downloading models")
        raise
