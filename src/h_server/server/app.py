from anyio import CancelScope, Event
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config
from typing import Optional

from .v1 import router as v1_router


class Server(object):
    def __init__(self) -> None:
        self._app = FastAPI()
        self._app.include_router(v1_router, prefix="/v1")
        self._shutdown_event: Optional[Event] = None

    async def start(self, host: str, port: int):
        assert self._shutdown_event is None, "Server has already been started."

        self._shutdown_event = Event()
        config = Config()
        config.bind = [f"{host}:{port}"]
        config.accesslog = "-"
        config.errorlog = "-"

        try:
            with CancelScope(shield=True):
                await serve(self._app, config, shutdown_trigger=self._shutdown_event.wait) # type: ignore
        finally:
            self._shutdown_event = None

    def stop(self):
        assert self._shutdown_event is not None, "Server has not been started."
        self._shutdown_event.set()

    @property
    def app(self):
        return self._app
