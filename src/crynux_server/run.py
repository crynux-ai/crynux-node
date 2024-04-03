import math
import signal
from typing import Optional

import anyio
from anyio import (
    TASK_STATUS_IGNORED,
    create_task_group,
    move_on_after,
    Event,
)
from anyio.abc import TaskStatus, TaskGroup

from crynux_server import db, log, utils
from crynux_server.config import get_config
from crynux_server.node_manager import NodeManager, set_node_manager
from crynux_server.server import Server, set_server

import logging
_logger = logging.getLogger(__name__)


class CrynuxRunner(object):
    def __init__(self) -> None:
        self.config = get_config()

        log.init(self.config)
        _logger.debug("Logger init completed.")

        self._server: Optional[Server] = None
        self._node_manager: Optional[NodeManager] = None
        self._tg: Optional[TaskGroup] = None

        self._shutdown_event: Optional[Event] = None
        signal.signal(signal.SIGINT, self._set_shutdown_event)
        signal.signal(signal.SIGTERM, self._set_shutdown_event)

    def _set_shutdown_event(self, *args):
        if self._shutdown_event is not None:
            self._shutdown_event.set()

    async def _wait_for_shutdown(self):
        if self._shutdown_event is not None:
            await self._shutdown_event.wait()
            await self.stop()

    async def run(self, task_status: TaskStatus[None] = TASK_STATUS_IGNORED):
        assert self._tg is None, "Crynux Server is running"

        self._shutdown_event = Event()

        await db.init(self.config.db)
        _logger.debug("DB init completed.")

        _logger.debug("Serving WebUI from: ", self.config.web_dist)
        self._server = Server(self.config.web_dist)
        set_server(self._server)
        _logger.debug("Server init completed.")

        gpu_info = await utils.get_gpu_info()
        gpu_name = gpu_info.model
        gpu_vram_gb = math.ceil(gpu_info.vram_total_mb / 1024)

        _logger.debug("Starting node manager...")

        self._node_manager = NodeManager(
            config=self.config, gpu_name=gpu_name, gpu_vram=gpu_vram_gb
        )
        set_node_manager(self._node_manager)

        _logger.debug("Node manager created.")

        try:
            async with create_task_group() as tg:
                self._tg = tg

                tg.start_soon(self._wait_for_shutdown)

                tg.start_soon(self._node_manager.run)
                if not self.config.headless:
                    await tg.start(
                        self._server.start,
                        self.config.server_host,
                        self.config.server_port,
                        self.config.log.level == "DEBUG",
                    )
                _logger.debug("Server started.")
                task_status.started()
        finally:
            with move_on_after(2, shield=True):
                await db.close()
            self._shutdown_event = None
            self._tg = None

    async def stop(self):
        if self._tg is None:
            return

        if self._server is not None and not self.config.headless:
            self._server.stop()
        if self._node_manager is not None:
            with move_on_after(10, shield=True):
                await self._node_manager.finish()
        self._tg.cancel_scope.cancel()


def run():
    try:
        runner = CrynuxRunner()
        anyio.run(runner.run)
    except KeyboardInterrupt:
        pass
