import asyncio
from functools import partial
from typing import Callable, Optional, TypeVar

from pebble import ProcessPool
from typing_extensions import ParamSpec

_default_process_executor: Optional[ProcessPool] = None


def init():
    global _default_process_executor

    assert _default_process_executor is None, "Process pool has been initilized"

    _default_process_executor = ProcessPool(max_workers=2)


def get_process_executor() -> ProcessPool:
    assert _default_process_executor is not None

    return _default_process_executor


P = ParamSpec("P")
T = TypeVar("T")


async def run_in_process(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    executor = get_process_executor()
    loop = asyncio.get_running_loop()
    inner = partial(func, *args, **kwargs)
    return await loop.run_in_executor(executor, inner, None)


def close():
    executor = get_process_executor()

    executor.stop()
    executor.join()
