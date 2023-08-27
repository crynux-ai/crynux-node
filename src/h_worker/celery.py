from celery import Celery

from .config import get_config

celery = Celery(
    "h-node", broker=get_config().celery.broker, backend=get_config.celery.backend
)
