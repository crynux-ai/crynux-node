from threading import RLock
from typing import Optional

from celery import Celery

from crynux_server.config import get_config

_celery: Optional[Celery] = None

_lock = RLock()


def get_celery():
    config = get_config()
    assert config.celery is not None, "Celery config not found."

    global _celery

    with _lock:
        if _celery is None:
            _celery = Celery(
                "crynux_worker", broker=config.celery.broker, backend=config.celery.backend
            )
    return _celery
