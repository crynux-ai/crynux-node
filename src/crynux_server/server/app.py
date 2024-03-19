from functools import partial
from typing import Optional

from anyio import TASK_STATUS_IGNORED, Event, create_task_group
from anyio.abc import TaskStatus
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from hypercorn.asyncio import serve
from hypercorn.config import Config

from .middleware import add_middleware
from .v1 import router as v1_router


class Server(object):
    def __init__(self, web_dist: str = "") -> None:
        self._app = FastAPI()
        self._app.include_router(v1_router, prefix="/manager")
        if web_dist != "":
            self._app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
        add_middleware(self._app)

        self._shutdown_event: Optional[Event] = None

    async def start(
        self,
        host: str,
        port: int,
        access_log: bool = True,
        *,
        task_status: TaskStatus[None] = TASK_STATUS_IGNORED,
    ):
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
                task_status.started()
        finally:
            self._shutdown_event = None

    def stop(self) -> None:
        assert self._shutdown_event is not None, "Server has not been started."
        self._shutdown_event.set()

    @property
    def app(self):
        return self._app
