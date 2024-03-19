import math
import signal
from typing import Optional

import anyio
from anyio import (
    TASK_STATUS_IGNORED,
    create_task_group,
    move_on_after,
    open_signal_receiver,
)
from anyio.abc import TaskStatus, TaskGroup

from crynux_server import db, log, utils
from crynux_server.config import get_config
from crynux_server.node_manager import NodeManager, set_node_manager
from crynux_server.server import Server, set_server


class CrynuxRunner(object):
    def __init__(self) -> None:
        self.config = get_config()

        self._server: Optional[Server] = None
        self._node_manager: Optional[NodeManager] = None
        self._tg: Optional[TaskGroup] = None

    async def run(self, task_status: TaskStatus[None] = TASK_STATUS_IGNORED):
        assert self._tg is None, "Crynux Server is running"
        log.init(self.config)

        await db.init(self.config.db)

        self._server = Server(self.config.web_dist)
        set_server(self._server)

        gpu_info = await utils.get_gpu_info()
        gpu_name = gpu_info.model
        gpu_vram_gb = math.ceil(gpu_info.vram_total_mb / 1024)

        self._node_manager = NodeManager(
            config=self.config, gpu_name=gpu_name, gpu_vram=gpu_vram_gb
        )
        set_node_manager(self._node_manager)

        async def signal_handler():
            with open_signal_receiver(signal.SIGINT, signal.SIGTERM) as signals:
                async for _ in signals:
                    await self.stop()
                    return

        try:
            async with create_task_group() as tg:
                self._tg = tg

                tg.start_soon(signal_handler)
                tg.start_soon(self._node_manager.run)
                if not self.config.headless:
                    await tg.start(
                        self._server.start,
                        self.config.server_host,
                        self.config.server_port,
                        self.config.log.level == "DEBUG",
                    )
                task_status.started()
        finally:
            with move_on_after(2, shield=True):
                await db.close()

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
