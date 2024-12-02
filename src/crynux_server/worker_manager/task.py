import asyncio
from typing import Any, AsyncGenerator, Callable

from anyio import create_memory_object_stream, create_task_group
from pydantic import BaseModel

from crynux_server.models import TaskType

from .error import TaskCancelled


class TaskInput(BaseModel):
    task_id_commitment: str
    task_name: str
    task_type: TaskType
    task_args: str


class TaskResult(object):
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


class TaskStreamResult(object):
    def __init__(self) -> None:
        sender, receiver = create_memory_object_stream()
        self._sender = sender
        self._receiver = receiver
        loop = asyncio.get_running_loop()
        self._future = loop.create_future()

        def _close_sender(_):
            self._sender.close()

        self._future.add_done_callback(_close_sender)

    async def _wait_future(self):
        return await self._future

    async def push_result(self, result):
        if not self._future.cancelled():
            await self._sender.send(result)

    async def get(self) -> AsyncGenerator[Any, None]:
        async with create_task_group() as tg:

            tg.start_soon(self._wait_future)

            async with self._receiver:
                async for result in self._receiver:
                    yield result

    def set_error(self, exc: Exception):
        if not self._future.cancelled():
            self._future.set_exception(exc)

    def cancel(self):
        if not self._future.cancelled():
            self._future.set_exception(TaskCancelled)

    def done(self):
        return self._future.done()

    def close(self):
        if not self._future.cancelled():
            self._future.set_result(None)

    def add_done_callback(self, callback: Callable[[asyncio.Future[Any]], None]):
        self._future.add_done_callback(callback)
