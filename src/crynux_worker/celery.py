from __future__ import annotations

import logging
from typing import cast, List

from celery import Celery
from celery.signals import celeryd_after_setup

from crynux_worker import log
from crynux_worker.config import get_config
from crynux_worker.prefetch import prefetch, ModelConfig, ProxyConfig
from crynux_worker.task import mock_inference, inference

_logger = logging.getLogger(__name__)

celery = Celery(
    "crynux_worker",
    broker=get_config().celery.broker,
    backend=get_config().celery.backend,
)

celery.task(name="inference", track_started=True)(inference)
celery.task(name="mock_inference", track_started=True)(mock_inference)


@celeryd_after_setup.connect
def prefetch_after_setup(_, __, **kwargs):
    config = get_config()
    log.init(config)

    _logger.info("Prefetch base models.")
    if config.task.preloaded_models is not None:
        preload_models = config.task.preloaded_models.model_dump()
        sd_base_models: List[ModelConfig] | None = preload_models.get("sd_base", None)
        gpt_base_models: List[ModelConfig] | None = preload_models.get("gpt_base", None)
        controlnet_models: List[ModelConfig] | None = preload_models.get("controlnet", None)
        vae_models: List[ModelConfig] | None = preload_models.get("vae", None)
    else:
        sd_base_models = None
        gpt_base_models = None
        controlnet_models = None
        vae_models = None

    if config.task.proxy is not None:
        proxy = config.task.proxy.model_dump()
        proxy = cast(ProxyConfig, proxy)
    else:
        proxy = None

    prefetch(
        hf_cache_dir=config.task.hf_cache_dir,
        external_cache_dir=config.task.external_cache_dir,
        script_dir=config.task.script_dir,
        sd_base_models=sd_base_models,
        gpt_base_models=gpt_base_models,
        controlnet_models=controlnet_models,
        vae_models=vae_models,
        proxy=proxy
    )
    _logger.info("Prefetching base models complete.")
