import signal

from anyio import create_task_group, move_on_after, open_signal_receiver, run
from anyio.abc import CancelScope
from web3.types import EventData

from h_server import db, models, log
from h_server.config import Config, get_config
from h_server.contracts import Contracts, set_contracts
from h_server.event_queue import DbEventQueue, EventQueue, set_event_queue
from h_server.join import node_join
from h_server.relay import Relay, set_relay
from h_server.server import Server
from h_server.task import DbTaskStateCache, TaskSystem, set_task_system
from h_server.task.task_runner import InferenceTaskRunner
from h_server.watcher import DbBlockNumberCache, EventWatcher, set_watcher


def _make_contracts(config: Config) -> Contracts:
    contracts = Contracts(
        provider_path=config.ethereum.provider, privkey=config.ethereum.privkey
    )
    set_contracts(contracts)
    return contracts


def _make_relay(config: Config) -> Relay:
    relay = Relay(base_url=config.relay_url, privkey=config.ethereum.privkey)
    set_relay(relay)
    return relay


async def _make_event_queue() -> EventQueue:
    queue = await DbEventQueue.from_db()
    set_event_queue(queue)
    return queue


def _make_watcher(contracts: Contracts, queue: EventQueue):
    watcher = EventWatcher.from_contracts(contracts)

    block_cache = DbBlockNumberCache()
    watcher.set_blocknumber_cache(block_cache)

    async def _push_event(event_data: EventData):
        event = models.load_event_from_contracts(event_data)
        await queue.put(event)

    watcher.watch_event(
        "task",
        "TaskCreated",
        callback=_push_event,
        filter_args={"selectedNode": contracts.account},
    )
    set_watcher(watcher)
    return watcher


def _make_task_system(queue: EventQueue, distributed: bool) -> TaskSystem:
    cache = DbTaskStateCache()

    system = TaskSystem(state_cache=cache, queue=queue, distributed=distributed)
    system.set_runner_cls(runner_cls=InferenceTaskRunner)

    set_task_system(system)
    return system


async def _main():
    config = get_config()

    log.init(config)
    await db.init(config.db)

    contracts = _make_contracts(config)
    await contracts.init(
        token_contract_address=config.ethereum.contract.token,
        node_contract_address=config.ethereum.contract.node,
        task_contract_address=config.ethereum.contract.task,
    )
    relay = _make_relay(config)
    queue = await _make_event_queue()

    watcher = _make_watcher(contracts=contracts, queue=queue)
    system = _make_task_system(queue=queue, distributed=config.distributed)

    if config.distributed:
        server = Server()
    else:
        server = None

    async def signal_handler(scope: CancelScope):
        with open_signal_receiver(signal.SIGINT, signal.SIGTERM) as signals:
            async for _ in signals:
                system.stop()
                if server is not None:
                    server.stop()
                watcher.stop()
                with move_on_after(2, shield=True):
                    await relay.close()
                scope.cancel()

    try:
        async with node_join(contracts=contracts):
            async with create_task_group() as tg:
                tg.start_soon(signal_handler, tg.cancel_scope)

                tg.start_soon(watcher.start)

                if server is not None:
                    tg.start_soon(server.start, config.server_host, config.server_port)

                tg.start_soon(system.start)
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
