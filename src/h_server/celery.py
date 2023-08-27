from functools import lru_cache

from celery import Celery

from h_server.config import get_config


@lru_cache()
def get_celery():
    config = get_config()
    celery = Celery(
        "h-node", broker=config.celery.broker, backend=config.celery.backend
    )
    return celery
