import logging
import os
from contextlib import asynccontextmanager
from typing import Optional, Type

from anyio import (Event, create_task_group, fail_after,
                   get_cancelled_exc_class, sleep, to_thread)
from anyio.abc import TaskGroup
from web3 import Web3
from web3.types import EventData

from h_server import models
from h_server.config import Config, wait_privkey
from h_server.contracts import Contracts, TxRevertedError, set_contracts
from h_server.event_queue import DbEventQueue, EventQueue, set_event_queue
from h_server.relay import Relay, WebRelay, set_relay
from h_server.task import (DbTaskStateCache, InferenceTaskRunner,
                           TaskStateCache, TaskSystem, set_task_state_cache,
                           set_task_system)
from h_server.watcher import (BlockNumberCache, DbBlockNumberCache,
                              EventWatcher, set_watcher)

from .state_cache import DbNodeStateCache, DbTxStateCache, StateCache

_logger = logging.getLogger(__name__)


async def _make_contracts(
    privkey: str,
    provider: str,
    token_contract_address: str,
    node_contract_address: str,
    task_contract_address: str,
) -> Contracts:
    contracts = Contracts(provider_path=provider, privkey=privkey)
    await contracts.init(
        token_contract_address=token_contract_address,
        node_contract_address=node_contract_address,
        task_contract_address=task_contract_address,
    )
    set_contracts(contracts)
    return contracts


def _make_relay(privkey: str, relay_url: str) -> Relay:
    relay = WebRelay(base_url=relay_url, privkey=privkey)
    set_relay(relay)
    return relay


def _make_event_queue(queue_cls: Type[EventQueue]) -> EventQueue:
    queue = queue_cls()
    set_event_queue(queue)
    return queue


def _make_watcher(
    contracts: Contracts,
    queue: EventQueue,
    block_number_cache_cls: Type[BlockNumberCache],
):
    watcher = EventWatcher.from_contracts(contracts)

    block_cache = block_number_cache_cls()
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


def _make_task_system(
    queue: EventQueue, distributed: bool, task_state_cache_cls: Type[TaskStateCache]
) -> TaskSystem:
    cache = task_state_cache_cls()
    set_task_state_cache(cache)

    system = TaskSystem(state_cache=cache, queue=queue, distributed=distributed)
    system.set_runner_cls(runner_cls=InferenceTaskRunner)

    set_task_system(system)
    return system


class NodeStateManager(object):
    def __init__(
        self,
        node_state_cache_cls: Type[StateCache[models.NodeState]] = DbNodeStateCache,
        tx_state_cache_cls: Type[StateCache[models.TxState]] = DbTxStateCache,
    ) -> None:
        self.node_state_cache = node_state_cache_cls()
        self.tx_state_cache = tx_state_cache_cls()

    async def get_node_state(self) -> models.NodeState:
        return await self.node_state_cache.get()

    async def get_tx_state(self) -> models.TxState:
        return await self.tx_state_cache.get()

    async def set_node_state(self, status: models.NodeStatus, message: str = ""):
        return await self.node_state_cache.set(
            models.NodeState(status=status, message=message)
        )

    async def set_tx_state(self, status: models.TxStatus, error: str = ""):
        return await self.tx_state_cache.set(models.TxState(status=status, error=error))


_default_state_manager: Optional[NodeStateManager] = None


def get_node_state_manager() -> NodeStateManager:
    assert _default_state_manager is not None, "Node state manager has not been set."

    return _default_state_manager


def set_node_state_manager(manager: NodeStateManager):
    global _default_state_manager

    _default_state_manager = manager


@asynccontextmanager
async def _wrap_tx_error(state_manager: NodeStateManager):
    try:
        yield
    except KeyboardInterrupt:
        raise
    except get_cancelled_exc_class():
        raise
    except (TxRevertedError, AssertionError, ValueError) as e:
        _logger.error(f"tx error {str(e)}")
        with fail_after(5, shield=True):
            await state_manager.set_tx_state(models.TxStatus.Error, str(e))
        raise
    except Exception as e:
        _logger.exception(e)
        _logger.error("unknown tx error")
        raise


async def start(contracts: Contracts, state_manager: NodeStateManager):
    async with _wrap_tx_error(state_manager):
        node_status = (await state_manager.get_node_state()).status
        tx_status = (await state_manager.get_tx_state()).status
        assert (
            node_status == models.NodeStatus.Stopped
        ), "Cannot start node. Node is not stopped."
        assert (
            tx_status != models.TxStatus.Pending
        ), "Cannot start node. Last transaction is in pending."

        node_amount = Web3.to_wei(400, "ether")
        balance = await contracts.token_contract.balance_of(contracts.account)
        if balance < node_amount:
            raise ValueError("Node token balance is not enough to join.")
        allowance = await contracts.token_contract.allowance(
            contracts.node_contract.address
        )
        if allowance < node_amount:
            waiter = await contracts.token_contract.approve(
                contracts.node_contract.address, node_amount
            )
            await waiter.wait()

        waiter = await contracts.node_contract.join()
        await state_manager.set_tx_state(models.TxStatus.Pending)

    async def wait():
        async with _wrap_tx_error(state_manager):
            await waiter.wait()
            await state_manager.set_tx_state(models.TxStatus.Success)

            status = await contracts.node_contract.get_node_status(contracts.account)
            local_status = models.convert_node_status(status)
            assert (
                local_status == models.NodeStatus.Running
            ), "Node status on chain is not running."
            await state_manager.set_node_state(local_status)

    return wait


async def stop(contracts: Contracts, state_manager: NodeStateManager):
    async with _wrap_tx_error(state_manager):
        node_status = (await state_manager.get_node_state()).status
        tx_status = (await state_manager.get_tx_state()).status
        assert (
            node_status == models.NodeStatus.Running
        ), "Cannot stop node. Node is not running."
        assert (
            tx_status != models.TxStatus.Pending
        ), "Cannot start node. Last transaction is in pending."

        waiter = await contracts.node_contract.quit()
        await state_manager.set_tx_state(models.TxStatus.Pending)

    async def wait():
        async with _wrap_tx_error(state_manager):
            await waiter.wait()
            await state_manager.set_tx_state(models.TxStatus.Success)

            while True:
                status = await contracts.node_contract.get_node_status(
                    contracts.account
                )
                local_status = models.convert_node_status(status)
                assert local_status in [
                    models.NodeStatus.Stopped,
                    models.NodeStatus.PendingStop,
                ], "Node status on chain is not stopped or pending."
                await state_manager.set_node_state(local_status)
                if local_status == models.NodeStatus.Stopped:
                    break

    return wait


async def pause(contracts: Contracts, state_manager: NodeStateManager):
    async with _wrap_tx_error(state_manager):
        node_status = (await state_manager.get_node_state()).status
        tx_status = (await state_manager.get_tx_state()).status
        assert (
            node_status == models.NodeStatus.Running
        ), "Cannot stop node. Node is not running."
        assert (
            tx_status != models.TxStatus.Pending
        ), "Cannot start node. Last transaction is in pending."

        waiter = await contracts.node_contract.pause()
        await state_manager.set_tx_state(models.TxStatus.Pending)

    async def wait():
        async with _wrap_tx_error(state_manager):
            await waiter.wait()
            await state_manager.set_tx_state(models.TxStatus.Success)

            while True:
                status = await contracts.node_contract.get_node_status(
                    contracts.account
                )
                local_status = models.convert_node_status(status)
                assert local_status in [
                    models.NodeStatus.Paused,
                    models.NodeStatus.PendingPause,
                ], "Node status on chain is not paused or pending"
                await state_manager.set_node_state(local_status)
                if local_status == models.NodeStatus.Paused:
                    break

    return wait


async def resume(contracts: Contracts, state_manager: NodeStateManager):
    async with _wrap_tx_error(state_manager):
        node_status = (await state_manager.get_node_state()).status
        tx_status = (await state_manager.get_tx_state()).status
        assert (
            node_status == models.NodeStatus.Paused
        ), "Cannot stop node. Node is not running."
        assert (
            tx_status != models.TxStatus.Pending
        ), "Cannot start node. Last transaction is in pending."

        waiter = await contracts.node_contract.resume()
        await state_manager.set_tx_state(models.TxStatus.Pending)

    async def wait():
        async with _wrap_tx_error(state_manager):
            await waiter.wait()
            await state_manager.set_tx_state(models.TxStatus.Success)

            status = await contracts.node_contract.get_node_status(contracts.account)
            local_status = models.convert_node_status(status)
            assert (
                local_status == models.NodeStatus.Running
            ), "Node status on chain is not running"
            await state_manager.set_node_state(local_status)

    return wait


class NodeManager(object):
    def __init__(
        self,
        config: Config,
        node_state_manager: Optional[NodeStateManager] = None,
        event_queue_cls: Type[EventQueue] = DbEventQueue,
        block_number_cache_cls: Type[BlockNumberCache] = DbBlockNumberCache,
        task_state_cache_cls: Type[TaskStateCache] = DbTaskStateCache,
        privkey: Optional[str] = None,
        event_queue: Optional[EventQueue] = None,
        contracts: Optional[Contracts] = None,
        relay: Optional[Relay] = None,
        watcher: Optional[EventWatcher] = None,
        task_system: Optional[TaskSystem] = None,
        restart_delay: float = 5,
    ) -> None:
        self.config = config
        if node_state_manager is None:
            node_state_manager = NodeStateManager()
            set_node_state_manager(node_state_manager)
        self.node_state_manager = node_state_manager

        self.event_queue_cls = event_queue_cls
        self.block_number_cache_cls = block_number_cache_cls
        self.task_state_cache_cls = task_state_cache_cls

        self._privkey = privkey
        self._event_queue = event_queue
        self._contracts = contracts
        self._relay = relay
        self._watcher = watcher
        self._task_system = task_system
        # restart delay equals 0 means do not restart and raise error, for test only
        self._restart_delay = restart_delay

        self._tg: Optional[TaskGroup] = None
        self._finish_event: Optional[Event] = None

    @property
    def finish_event(self) -> Event:
        if self._finish_event is None:
            self._finish_event = Event()
        return self._finish_event

    async def _init_components(self):
        _logger.info("Initializing node manager components.")
        if self._contracts is None or self._relay is None:
            if self._privkey is None:
                self._privkey = await wait_privkey()

            if self._contracts is None:
                self._contracts = await _make_contracts(
                    privkey=self._privkey,
                    provider=self.config.ethereum.provider,
                    token_contract_address=self.config.ethereum.contract.token,
                    node_contract_address=self.config.ethereum.contract.node,
                    task_contract_address=self.config.ethereum.contract.task,
                )
            if self._relay is None:
                self._relay = _make_relay(self._privkey, self.config.relay_url)

        if self._watcher is None or self._task_system is None:
            if self._event_queue is None:
                self._event_queue = _make_event_queue(self.event_queue_cls)
            if self._watcher is None:
                self._watcher = _make_watcher(
                    contracts=self._contracts,
                    queue=self._event_queue,
                    block_number_cache_cls=self.block_number_cache_cls,
                )
            if self._task_system is None:
                self._task_system = _make_task_system(
                    queue=self._event_queue,
                    distributed=self.config.distributed,
                    task_state_cache_cls=self.task_state_cache_cls,
                )
        _logger.info("Node manager components initializing complete.")

    async def _init(self):
        status = (await self.node_state_manager.get_node_state()).status
        if status in (models.NodeStatus.Init, models.NodeStatus.Error):
            _logger.info("Initialize node manager")
            await self.node_state_manager.set_node_state(models.NodeStatus.Init)
            # clear tx error when restart
            await self.node_state_manager.set_tx_state(models.TxStatus.Success)

            if not self.config.distributed:
                from h_worker.prefetch import prefetch

                assert (
                    self.config.task_config is not None
                ), "Task config is None in non-distributed version"

                await to_thread.run_sync(
                    prefetch,
                    self.config.task_config.pretrained_models_dir,
                    os.path.join(self.config.task_config.script_dir, "huggingface"),
                    self.config.task_config.script_dir,
                    cancellable=True,
                )

            await self.node_state_manager.set_node_state(models.NodeStatus.Stopped)
            _logger.info("Node manager initializing complete.")

    async def _run(self):
        assert self._tg is None, "Node manager is running."

        try:
            async with create_task_group() as tg:
                self._tg = tg

                async with create_task_group() as init_tg:
                    init_tg.start_soon(self._init_components)
                    init_tg.start_soon(self._init)

                assert self._watcher is not None
                assert self._task_system is not None

                tg.start_soon(self._watcher.start)
                tg.start_soon(self._task_system.start)
        finally:
            self._tg = None
            self._task_system = None
            self._watcher = None
            self._relay = None
            self._contracts = None

    async def run(self):
        assert self._tg is None, "Node manager is running."

        while not self.finish_event.is_set():
            try:
                await self._run()
            except KeyboardInterrupt:
                raise
            except get_cancelled_exc_class():
                raise
            except Exception as e:
                _logger.exception(e)
                _logger.error(f"Node manager error: {str(e)}")
                with fail_after(5, shield=True):
                    await self.node_state_manager.set_node_state(
                        models.NodeStatus.Error, str(e)
                    )
                if self._restart_delay > 0:
                    _logger.error(
                        f"Node manager restart in {self._restart_delay} seconds"
                    )
                    await sleep(self._restart_delay)
                else:
                    raise e

    async def finish(self):
        self.finish_event.set()

        if self._relay is not None:
            with fail_after(2, shield=True):
                await self._relay.close()
        if self._watcher is not None:
            self._watcher.stop()
        if self._task_system is not None:
            self._task_system.stop()
        if self._tg is not None and not self._tg.cancel_scope.cancel_called:
            self._tg.cancel_scope.cancel()

        self._finish_event = None


_node_manager: Optional[NodeManager] = None


def get_node_manager() -> NodeManager:
    assert _node_manager is not None, "Node manager has not been set."

    return _node_manager


def set_node_manager(manager: NodeManager):
    global _node_manager

    _node_manager = manager
