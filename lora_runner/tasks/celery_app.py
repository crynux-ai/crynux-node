from celery import Celery
from celery.signals import after_task_publish
from lora_runner.config import config

celery_app = Celery(
    __name__,
    broker=config['celery']['broker'],
    backend=config['celery']['backend']
)


@after_task_publish.connect
def update_sent_state(sender=None, headers=None, **kwargs):
    # the task may not exist if sent using `send_task` which
    # sends tasks by name, so fall back to the default result backend
    # if that is the case.
    task = celery_app.tasks.get(sender)
    backend = task.backend if task else celery_app.backend

    backend.store_result(headers['id'], None, "SENT")
