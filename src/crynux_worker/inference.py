from __future__ import annotations

from datetime import datetime
import json
import logging
import os
import subprocess
from typing import List

from crynux_worker import config, utils
from crynux_worker.config import ModelConfig, ProxyConfig


_logger = logging.getLogger(__name__)


def call_inference_script(
    task_args_str: str,
    output_dir: str,
    hf_cache_dir: str,
    external_cache_dir: str,
    script_dir: str,
    base_models: List[ModelConfig] | None = None,
    controlnet_models: List[ModelConfig] | None = None,
    vae_models: List[ModelConfig] | None = None,
    proxy: ProxyConfig | None = None,
):
    envs = config.set_env(
        hf_cache_dir=hf_cache_dir,
        external_cache_dir=external_cache_dir,
        base_models=base_models,
        controlnet_models=controlnet_models,
        vae_models=vae_models,
        proxy=proxy,
    )

    start_ts = datetime.now()
    args = utils.get_exe_head("inference", script_dir)
    args.extend(["0", output_dir, task_args_str])

    _logger.info(f"Start inference models, save in {output_dir}")
    subprocess.check_call(args, env=envs)
    complete_ts = datetime.now()
    _logger.info(f"Inference models complete: {str(complete_ts - start_ts)}")


def inference(
    task_args_str: str,
    output_dir: str,
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

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    try:
        call_inference_script(
            task_args_str=task_args_str,
            output_dir=output_dir,
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
        _logger.error("Inference error")
        raise
