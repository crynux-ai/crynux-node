from functools import partial
from typing import Optional

from anyio import Event, create_task_group
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from hypercorn.asyncio import serve
from hypercorn.config import Config

from .v1 import router as v1_router
from .middleware import add_middleware


class Server(object):
    def __init__(self, web_dist: str = "") -> None:
        self._app = FastAPI()
        self._app.include_router(v1_router, prefix="/manager")
        if web_dist != "":
            self._app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
        add_middleware(self._app)

        self._shutdown_event: Optional[Event] = None

    async def start(self, host: str, port: int, access_log: bool = True):
        assert self._shutdown_event is None, "Server has already been started."

        self._shutdown_event = Event()
        config = Config()
        config.bind = [f"{host}:{port}"]
        if access_log:
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
