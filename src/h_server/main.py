import signal

from anyio import create_task_group, move_on_after, open_signal_receiver, run
from anyio.abc import CancelScope

from h_server import db, log
from h_server.config import get_config
from h_server.server import Server
from h_server.node_manager import NodeManager, set_node_manager



async def _main():
    config = get_config()

    log.init(config)

    await db.init(config.db)

    server = Server(config.web_dist)
    node_manager = NodeManager(config=config)
    set_node_manager(node_manager)

    async def signal_handler(scope: CancelScope):
        with open_signal_receiver(signal.SIGINT, signal.SIGTERM) as signals:
            async for _ in signals:
                if not config.headless:
                    server.stop()
                with move_on_after(10, shield=True):
                    await node_manager.finish()
                scope.cancel()
                return

    try:
        async with create_task_group() as tg:
            tg.start_soon(signal_handler, tg.cancel_scope)

            tg.start_soon(node_manager.run)
            
            if not config.headless:
                tg.start_soon(server.start, config.server_host, config.server_port, config.log.level == "DEBUG")
    finally:
        with move_on_after(2, shield=True):
            await db.close()


def main():
    try:
        run(_main)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
