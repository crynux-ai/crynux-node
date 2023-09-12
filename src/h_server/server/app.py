from functools import partial
from typing import Optional

from anyio import Event, create_task_group
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config

from .v1 import router as v1_router


class Server(object):
    def __init__(self) -> None:
        self._app = FastAPI()
        self._app.include_router(v1_router)
        self._shutdown_event: Optional[Event] = None

    async def start(self, host: str, port: int):
        assert self._shutdown_event is None, "Server has already been started."

        self._shutdown_event = Event()
        config = Config()
        config.bind = [f"{host}:{port}"]
        config.accesslog = "-"
        config.errorlog = "-"

        try:
            async with create_task_group() as tg:
                serve_func = partial(serve, self._app, config, shutdown_trigger=self._shutdown_event.wait)  # type: ignore
                tg.start_soon(serve_func)
        finally:
            self._shutdown_event = None

    def stop(self):
        assert self._shutdown_event is not None, "Server has not been started."
        self._shutdown_event.set()

    @property
    def app(self):
        return self._app
