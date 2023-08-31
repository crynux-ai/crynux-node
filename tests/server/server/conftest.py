import pytest

from h_server.config import Config, set_config
from h_server.event_queue import MemoryEventQueue, set_event_queue
from h_server.task import TaskSystem, TestTaskRunner, set_task_system
from h_server.task.state_cache import MemoryTaskStateCache


@pytest.fixture(scope="module", autouse=True)
async def init():
    test_config = Config.model_validate(
        {
            "log": {"dir": "logs", "level": "INFO"},
            "ethereum": {
                "privkey": "",
                "provider": "",
                "contract": {"token": "", "node": "", "task": ""},
            },
            "task_dir": "task",
            "db": "",
            "relay_url": "",
            "celery": {"broker": "", "backend": ""},
        }
    )
    set_config(test_config)
    queue = MemoryEventQueue()
    set_event_queue(queue)

    cache = MemoryTaskStateCache()

    system = TaskSystem(state_cache=cache, queue=queue)
    system.set_runner_cls(TestTaskRunner)

    set_task_system(system)
