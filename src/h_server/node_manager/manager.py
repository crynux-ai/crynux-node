import logging
import os
from typing import Optional, Type

from anyio import (Event, create_task_group, fail_after,
                   get_cancelled_exc_class, to_thread)
from anyio.abc import TaskGroup
from web3 import Web3
from web3.types import EventData

from h_server import models
from h_server.config import Config, wait_privkey
from h_server.contracts import Contracts, set_contracts
from h_server.event_queue import DbEventQueue, EventQueue, set_event_queue
from h_server.relay import Relay, WebRelay, set_relay
from h_server.task import (DbTaskStateCache, InferenceTaskRunner,
                           TaskStateCache, TaskSystem, set_task_state_cache,
                           set_task_system)
from h_server.watcher import (BlockNumberCache, DbBlockNumberCache,
                              EventWatcher, set_watcher)

from .state_cache import DbNodeStateCache, NodeStateCache, set_node_state_cache

_logger = logging.getLogger(__name__)


def _make_contracts(privkey: str, provider: str) -> Contracts:
    contracts = Contracts(provider_path=provider, privkey=privkey)
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


class NodeManager(object):
    def __init__(
        self,
        config: Config,
        event_queue_cls: Type[EventQueue] = DbEventQueue,
        node_state_cache_cls: Type[NodeStateCache] = DbNodeStateCache,
        block_number_cache_cls: Type[BlockNumberCache] = DbBlockNumberCache,
        task_state_cache_cls: Type[TaskStateCache] = DbTaskStateCache,
        privkey: Optional[str] = None,
        event_queue: Optional[EventQueue] = None,
        contracts: Optional[Contracts] = None,
        relay: Optional[Relay] = None,
        watcher: Optional[EventWatcher] = None,
        task_system: Optional[TaskSystem] = None,
    ) -> None:
        self.config = config
        self.node_state_cache = node_state_cache_cls()
        set_node_state_cache(self.node_state_cache)

        self.event_queue_cls = event_queue_cls
        self.block_number_cache_cls = block_number_cache_cls
        self.task_state_cache_cls = task_state_cache_cls

        self._privkey = privkey
        self._event_queue = event_queue
        self._contracts = contracts
        self._relay = relay
        self._watcher = watcher
        self._task_system = task_system

        self._tg: Optional[TaskGroup] = None
        self._finish_event: Optional[Event] = None

    @property
    def finish_event(self) -> Event:
        if self._finish_event is None:
            self._finish_event = Event()
        return self._finish_event

    async def get_state(self) -> models.NodeState:
        current_state = await self.node_state_cache.get()
        if (
            current_state.status == models.NodeStatus.Pending
            and self._contracts is not None
        ):
            status = await self._contracts.node_contract.get_node_status(
                self._contracts.account
            )
            remote_status = models.convert_node_status(status)
            if remote_status != current_state.status:
                await self.node_state_cache.set(models.NodeState(status=remote_status))
                current_state.status = remote_status
        return current_state

    async def _get_status(self) -> models.NodeStatus:
        return (await self.get_state()).status

    async def _set_status(self, status: models.NodeStatus):
        await self.node_state_cache.set(models.NodeState(status=status))

    async def _set_error(self, error_msg: str):
        await self.node_state_cache.set(
            models.NodeState(
                status=models.NodeStatus.Error,
                message=error_msg,
            )
        )

    async def _init_components(self):
        _logger.info("Initializing node manager components.")
        if self._contracts is None or self._relay is None:
            if self._privkey is None:
                self._privkey = await wait_privkey()

            if self._contracts is None:
                self._contracts = _make_contracts(self._privkey, self.config.ethereum.provider)
                await self._contracts.init()
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
        status = await self._get_status()
        if status in (models.NodeStatus.Init, models.NodeStatus.Error):
            _logger.info("Initialize node manager")

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

            await self._set_status(models.NodeStatus.Stopped)
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
                with fail_after(2, shield=True):
                    await self._set_error(str(e))

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

    async def start(self):
        assert (
            await self._get_status() == models.NodeStatus.Stopped
        ), "Cannot start node. Node should be stopped."

        assert self._contracts is not None, "Contracts is not initialized."
        status = await self._contracts.node_contract.get_node_status(
            self._contracts.account
        )
        assert (
            status == models.ChainNodeStatus.QUIT
        ), "Cannot start node. Node should be stopped."
        node_amount = Web3.to_wei(400, "ether")
        balance = await self._contracts.token_contract.balance_of(
            self._contracts.account
        )
        if balance < node_amount:
            raise ValueError("Node token balance is not enough to join.")
        allowance = await self._contracts.token_contract.allowance(
            self._contracts.node_contract.address
        )
        if allowance < node_amount:
            waiter = await self._contracts.token_contract.approve(
                self._contracts.node_contract.address, node_amount
            )
            await waiter.wait()

        waiter = await self._contracts.node_contract.join()
        await waiter.wait()
        status = await self._contracts.node_contract.get_node_status(
            self._contracts.account
        )
        local_status = models.convert_node_status(status)
        assert (
            local_status == models.NodeStatus.Running
        ), f"Error node status from chain {status}"
        await self._set_status(local_status)

    async def stop(self):
        assert (
            await self._get_status() == models.NodeStatus.Running
        ), "Cannot start node. Node should be running."
        assert self._contracts is not None, "Contracts is not initialized."
        status = await self._contracts.node_contract.get_node_status(
            self._contracts.account
        )
        assert status in [
            models.ChainNodeStatus.AVAILABLE,
            models.ChainNodeStatus.BUSY,
        ], "Cannot stop node. Node should be running."
        waiter = await self._contracts.node_contract.quit()
        await waiter.wait()
        status = await self._contracts.node_contract.get_node_status(
            self._contracts.account
        )
        local_status = models.convert_node_status(status)
        assert local_status in [
            models.NodeStatus.Stopped,
            models.NodeStatus.Pending,
        ], f"Error node status from chain {status}"
        await self._set_status(local_status)

    async def resume(self):
        assert (
            await self._get_status() == models.NodeStatus.Paused
        ), "Cannot resume node. Node should be paused."
        assert self._contracts is not None, "Contracts is not initialized."
        status = await self._contracts.node_contract.get_node_status(
            self._contracts.account
        )
        assert (
            status == models.ChainNodeStatus.PAUSED
        ), "Cannot resume node. Node should be paused."
        waiter = await self._contracts.node_contract.resume()
        await waiter.wait()
        status = await self._contracts.node_contract.get_node_status(
            self._contracts.account
        )
        local_status = models.convert_node_status(status)
        assert (
            local_status == models.NodeStatus.Running
        ), f"Error node status from chain {status}"
        await self._set_status(local_status)

    async def pause(self):
        assert (
            await self._get_status() == models.NodeStatus.Running
        ), "Cannot pause node. Node should be running."
        assert self._contracts is not None, "Contracts is not initialized."
        status = await self._contracts.node_contract.get_node_status(
            self._contracts.account
        )
        assert status in [
            models.ChainNodeStatus.AVAILABLE,
            models.ChainNodeStatus.BUSY,
        ], "Cannot pause node. Node should be running."
        waiter = await self._contracts.node_contract.pause()
        await waiter.wait()
        status = await self._contracts.node_contract.get_node_status(
            self._contracts.account
        )
        local_status = models.convert_node_status(status)
        assert local_status in [
            models.NodeStatus.Paused,
            models.NodeStatus.Pending,
        ], f"Error node status from chain {status}"
        await self._set_status(local_status)


_node_manager: Optional[NodeManager] = None


def get_node_manager() -> NodeManager:
    assert _node_manager is not None, "Node manager has not been set."

    return _node_manager


def set_node_manager(manager: NodeManager):
    global _node_manager

    _node_manager = manager
