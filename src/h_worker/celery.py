import logging

from celery import Celery
from celery.signals import celeryd_after_setup

from h_worker import log
from h_worker.config import get_config
from h_worker.prefetch import prefetch
from h_worker.task import mock_lora_inference, sd_lora_inference

_logger = logging.getLogger(__name__)

celery = Celery(
    "h_worker",
    broker=get_config().celery.broker,
    backend=get_config().celery.backend,
)

celery.task(name="sd_lora_inference", track_started=True)(sd_lora_inference)
celery.task(name="mock_lora_inference", track_started=True)(mock_lora_inference)


@celeryd_after_setup.connect
def prefetch_after_setup(_, __, **kwargs):
    config = get_config()
    log.init(config)

    _logger.info("Prefetch base models.")
    prefetch(
        config.task.hf_cache_dir,
        config.task.external_cache_dir,
        config.task.script_dir,
    )
    _logger.info("Prefetching base models complete.")
