from celery import Celery

from .config import get_config

celery = Celery(
    "h_worker",
    broker=get_config().celery.broker,
    backend=get_config().celery.backend,
    include=["h_worker.task"],
)
