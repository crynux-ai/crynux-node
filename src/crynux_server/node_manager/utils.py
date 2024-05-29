from __future__ import annotations

from functools import partial
from typing import List

from anyio import from_thread, to_process, to_thread

from crynux_server import models
from crynux_worker.models import ModelConfig, ProxyConfig

from .state_cache import ManagerStateCache


async def prefetch_in_thread(
    state_cache: ManagerStateCache,
    hf_cache_dir: str,
    external_cache_dir: str,
    script_dir: str,
    sd_base_models: List[ModelConfig] | None = None,
    gpt_base_models: List[ModelConfig] | None = None,
    controlnet_models: List[ModelConfig] | None = None,
    vae_models: List[ModelConfig] | None = None,
    proxy: ProxyConfig | None = None,
):

    def prefetch_process_callback(current_models: int, total_models: int):
        func = partial(
            state_cache.set_node_state,
            status=models.NodeStatus.Init,
            init_message=f"Downloading models............ ({current_models}/{total_models})",
        )
        from_thread.run(func)

    from crynux_worker.prefetch import prefetch

    await to_thread.run_sync(
        prefetch,
        hf_cache_dir,
        external_cache_dir,
        script_dir,
        sd_base_models,
        gpt_base_models,
        controlnet_models,
        vae_models,
        proxy,
        prefetch_process_callback,
        cancellable=True,
    )


def _inference(
    task_args_str: str,
    output_dir: str,
    hf_cache_dir: str,
    external_cache_dir: str,
    script_dir: str,
    proxy: ProxyConfig | None = None,
):
    from crynux_worker.inference import inference

    inference(
        task_args_str,
        output_dir,
        hf_cache_dir,
        external_cache_dir,
        script_dir,
        proxy,
    )


async def inference_in_process(
    task_args_str: str,
    output_dir: str,
    hf_cache_dir: str,
    external_cache_dir: str,
    script_dir: str,
    proxy: ProxyConfig | None = None,
):
    await to_process.run_sync(
        _inference,
        task_args_str,
        output_dir,
        hf_cache_dir,
        external_cache_dir,
        script_dir,
        proxy,
        cancellable=True,
    )
