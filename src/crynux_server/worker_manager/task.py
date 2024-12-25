import asyncio
from typing import Any, Callable

from .error import TaskCancelled

class TaskFuture(object):
    def __init__(self) -> None:
        loop = asyncio.get_running_loop()
        self._future = loop.create_future()

    def set_result(self, result):
        if not self._future.cancelled():
            self._future.set_result(result)

    def set_error(self, exc: Exception):
        if not self._future.cancelled():
            self._future.set_exception(exc)

    def cancel(self):
        if not self._future.cancelled():
            self._future.set_exception(TaskCancelled)

    def add_done_callback(self, callback: Callable[[asyncio.Future[Any]], None]):
        self._future.add_done_callback(callback)

    async def get(self):
        return await self._future

    def done(self):
        return self._future.done()
