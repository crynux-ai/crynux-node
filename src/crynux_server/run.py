import math
import signal
import os.path
from typing import Optional

import anyio
from anyio import (
    TASK_STATUS_IGNORED,
    create_task_group,
    move_on_after,
    sleep,
    Event,
)
from anyio.abc import TaskStatus, TaskGroup

from crynux_server import db, log, utils
from crynux_server.config import get_config
from crynux_server.node_manager import NodeManager, set_node_manager
from crynux_server.worker_manager import WorkerManager, set_worker_manager
from crynux_server.server import Server, set_server

import logging

_logger = logging.getLogger(__name__)


class CrynuxRunner(object):
    def __init__(self) -> None:
        self.config = get_config()

        log.init(
            self.config.log.dir,
            self.config.log.level,
            self.config.log.filename,
            self.config.distributed,
        )
        _logger.debug("Logger init completed.")

        self._server: Optional[Server] = None
        self._node_manager: Optional[NodeManager] = None
        self._tg: Optional[TaskGroup] = None

        self._shutdown_event: Optional[Event] = None
        self._should_shutdown = False
        signal.signal(signal.SIGINT, self._shutdown_signal_handler)
        signal.signal(signal.SIGTERM, self._shutdown_signal_handler)

    def _shutdown_signal_handler(self, *args):
        self._should_shutdown = True

    async def _check_should_shutdown(self):
        while not self._should_shutdown:
            await sleep(0.1)
        self._set_shutdown_event()

    def _set_shutdown_event(self):
        if self._shutdown_event is not None:
            self._shutdown_event.set()

    async def _wait_for_shutdown(self):
        if self._shutdown_event is not None:
            await self._shutdown_event.wait()
            await self._stop()

    async def run(self, task_status: TaskStatus[None] = TASK_STATUS_IGNORED):
        assert self._tg is None, "Crynux Server is running"

        _logger.info("Starting Crynux server")

        self._shutdown_event = Event()

        await db.init(self.config.db)
        _logger.info("DB init completed.")

        worker_manager = WorkerManager()
        set_worker_manager(worker_manager)

        _logger.info(f"Serving WebUI from: {os.path.abspath(self.config.web_dist)}")
        self._server = Server(self.config.web_dist)
        set_server(self._server)
        _logger.info("Web server init completed.")

        gpu_info = await utils.get_gpu_info()
        gpu_name = gpu_info.model
        gpu_vram_gb = math.ceil(gpu_info.vram_total_mb / 1024)

        _logger.info("Starting node manager...")

        self._node_manager = NodeManager(
            config=self.config, gpu_name=gpu_name, gpu_vram=gpu_vram_gb
        )
        set_node_manager(self._node_manager)

        _logger.info("Node manager created.")

        try:
            async with create_task_group() as tg:
                self._tg = tg

                tg.start_soon(self._check_should_shutdown)
                tg.start_soon(self._wait_for_shutdown)

                tg.start_soon(self._node_manager.run)
                if not self.config.headless:
                    await tg.start(
                        self._server.start,
                        self.config.server_host,
                        self.config.server_port,
                        self.config.log.level == "DEBUG",
                    )
                _logger.info("Crynux server started.")
                task_status.started()
        finally:
            with move_on_after(2, shield=True):
                await db.close()
            self._shutdown_event = None
            self._tg = None
            _logger.info("Crynux server stopped")

    async def _stop(self):
        _logger.info("Stopping crynux server")
        if self._tg is None:
            return

        if self._server is not None and not self.config.headless:
            self._server.stop()
        if self._node_manager is not None:
            with move_on_after(10, shield=True):
                await self._node_manager.finish()
        self._tg.cancel_scope.cancel()

    async def stop(self):
        self._set_shutdown_event()


def run():
    try:
        runner = CrynuxRunner()
        anyio.run(runner.run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
