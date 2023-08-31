from celery import Celery

from h_worker.config import get_config
from h_worker.task import sd_lora_inference, mock_lora_inference

celery = Celery(
    "h_worker",
    broker=get_config().celery.broker,
    backend=get_config().celery.backend,
)

celery.task(name="sd_lora_inference", track_started=True)(sd_lora_inference)
celery.task(name="mock_lora_inference", track_started=True)(mock_lora_inference)
