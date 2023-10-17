import logging
import os
from contextlib import asynccontextmanager
from typing import Optional, Type

from anyio import (
    Event,
    create_task_group,
    fail_after,
    get_cancelled_exc_class,
    sleep,
    to_thread,
)
from anyio.abc import TaskGroup
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_fixed,
)
from web3 import Web3
from web3.types import EventData

from h_server import models
from h_server.config import Config, wait_privkey
from h_server.contracts import Contracts, set_contracts
from h_server.event_queue import DbEventQueue, EventQueue, set_event_queue
from h_server.relay import Relay, WebRelay, set_relay
from h_server.task import (
    DbTaskStateCache,
    InferenceTaskRunner,
    TaskStateCache,
    TaskSystem,
    set_task_state_cache,
    set_task_system,
)
from h_server.watcher import (
    BlockNumberCache,
    DbBlockNumberCache,
    EventWatcher,
    set_watcher,
)

from .state_cache import (
    DbNodeStateCache,
    DbTxStateCache,
    ManagerStateCache,
    StateCache,
    set_manager_state_cache,
)
from .state_manager import NodeStateManager, set_node_state_manager

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
    retry_count: int = 3,
    retry_delay: float = 30,
):
    watcher = EventWatcher.from_contracts(
        contracts, retry_count=retry_count, retry_delay=retry_delay
    )

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


def _make_node_state_manager(
    state_cache: ManagerStateCache,
    contracts: Contracts,
    retry_count: int = 3,
    retry_delay: float = 30,
):
    state_manager = NodeStateManager(
        state_cache=state_cache,
        contracts=contracts,
        retry_count=retry_count,
        retry_delay=retry_delay,
    )
    set_node_state_manager(state_manager)
    return state_manager


class NodeManager(object):
    def __init__(
        self,
        config: Config,
        event_queue_cls: Type[EventQueue] = DbEventQueue,
        block_number_cache_cls: Type[BlockNumberCache] = DbBlockNumberCache,
        task_state_cache_cls: Type[TaskStateCache] = DbTaskStateCache,
        node_state_cache_cls: Type[StateCache[models.NodeState]] = DbNodeStateCache,
        tx_state_cache_cls: Type[StateCache[models.TxState]] = DbTxStateCache,
        manager_state_cache: Optional[ManagerStateCache] = None,
        privkey: Optional[str] = None,
        event_queue: Optional[EventQueue] = None,
        contracts: Optional[Contracts] = None,
        relay: Optional[Relay] = None,
        node_state_manager: Optional[NodeStateManager] = None,
        watcher: Optional[EventWatcher] = None,
        task_system: Optional[TaskSystem] = None,
        retry_count: int = 3,
        retry_delay: float = 30,
    ) -> None:
        self.config = config

        self.event_queue_cls = event_queue_cls
        self.block_number_cache_cls = block_number_cache_cls
        self.task_state_cache_cls = task_state_cache_cls
        if manager_state_cache is None:
            manager_state_cache = ManagerStateCache(
                node_state_cache_cls=node_state_cache_cls,
                tx_state_cache_cls=tx_state_cache_cls,
            )
            set_manager_state_cache(manager_state_cache)
        self.state_cache = manager_state_cache

        self._privkey = privkey
        self._event_queue = event_queue
        self._contracts = contracts
        self._relay = relay
        self._node_state_manager = node_state_manager
        self._watcher = watcher
        self._task_system = task_system

        self._retry_count = retry_count
        self._retry_delay = retry_delay

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

        if self._node_state_manager is None:
            self._node_state_manager = _make_node_state_manager(
                state_cache=self.state_cache,
                contracts=self._contracts,
                retry_count=self._retry_count,
                retry_delay=self._retry_delay,
            )

        if self._watcher is None or self._task_system is None:
            if self._event_queue is None:
                self._event_queue = _make_event_queue(self.event_queue_cls)
            if self._watcher is None:
                self._watcher = _make_watcher(
                    contracts=self._contracts,
                    queue=self._event_queue,
                    block_number_cache_cls=self.block_number_cache_cls,
                    retry_count=self._retry_count,
                    retry_delay=self._retry_delay
                )
            if self._task_system is None:
                self._task_system = _make_task_system(
                    queue=self._event_queue,
                    distributed=self.config.distributed,
                    task_state_cache_cls=self.task_state_cache_cls,
                )
        _logger.info("Node manager components initializing complete.")

    async def _init(self):
        status = (await self.state_cache.get_node_state()).status
        if status in (models.NodeStatus.Init, models.NodeStatus.Error):
            _logger.info("Initialize node manager")
            await self.state_cache.set_node_state(models.NodeStatus.Init)
            # clear tx error when restart
            await self.state_cache.set_tx_state(models.TxStatus.Success)

            if not self.config.distributed:
                from h_worker.prefetch import prefetch

                assert (
                    self.config.task_config is not None
                ), "Task config is None in non-distributed version"

                await to_thread.run_sync(
                    prefetch,
                    self.config.task_config.hf_cache_dir,
                    self.config.task_config.external_cache_dir,
                    self.config.task_config.script_dir,
                    cancellable=True,
                )

            _logger.info("Node manager initializing complete.")

    async def _recover(self):
        assert self._contracts is not None
        assert self._task_system is not None

        task_id = await self._contracts.task_contract.get_node_task(
            self._contracts.account
        )
        if task_id == 0:
            return
        if await self._task_system.state_cache.has(task_id):
            return

        task = await self._contracts.task_contract.get_task(task_id=task_id)
        round = task.selected_nodes.index(self._contracts.account)
        state = models.TaskState(
            task_id=task_id, round=round, status=models.TaskStatus.Pending
        )

        events = []
        # task created
        event = models.TaskCreated(
            task_id=task_id,
            creator=Web3.to_checksum_address(task.creator),
            selected_node=self._contracts.account,
            task_hash=Web3.to_hex(task.task_hash),
            data_hash=Web3.to_hex(task.data_hash),
            round=round,
        )
        events.append(event)

        # has submitted result commitment
        if round < len(task.commitments) and task.commitments[round] != bytes([0] * 32):
            assert self.config.last_result is not None, (
                f"Task {task_id} has submitted result commitment, but last result has not found in config."
                " Please set the result in config file to rerun the task."
            )
            state.result = bytes.fromhex(self.config.last_result[2:])
            event = models.TaskResultCommitmentsReady(task_id=task_id)
            events.append(event)

        # has disclosed
        if round < len(task.results) and task.results[round] != b"":
            state.disclosed = True
            # task is success
            if task.result_node != "0x" + bytes([0] * 20).hex():
                result = task.results[round]
                event = models.TaskSuccess(
                    task_id=task_id,
                    result=Web3.to_hex(result),
                    result_node=Web3.to_checksum_address(task.result_node),
                )
                state.result = result
                events.append(event)

        for event in events:
            await self._task_system.event_queue.put(event=event)
        await self._task_system.state_cache.dump(state)

    async def _run(self):
        assert self._tg is None, "Node manager is running."

        try:
            async with create_task_group() as tg:
                self._tg = tg

                async with create_task_group() as init_tg:
                    init_tg.start_soon(self._init_components)
                    init_tg.start_soon(self._init)

                await self._recover()

                assert self._node_state_manager is not None
                assert self._watcher is not None
                assert self._task_system is not None

                tg.start_soon(self._node_state_manager.start_sync)
                tg.start_soon(self._watcher.start)
                tg.start_soon(self._task_system.start)
        finally:
            self._tg = None

    async def run(self):
        assert self._tg is None, "Node manager is running."

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
                await self.state_cache.set_node_state(models.NodeStatus.Error, str(e))
            await self.finish()

    async def finish(self):
        if self._relay is not None:
            with fail_after(2, shield=True):
                await self._relay.close()
            self._relay = None
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
        if self._task_system is not None:
            self._task_system.stop()
            self._task_system = None
        if self._node_state_manager is not None:
            self._node_state_manager.stop_sync()
            self._node_state_manager = None
        if self._contracts is not None:
            self._contracts = None
        if self._tg is not None and not self._tg.cancel_scope.cancel_called:
            self._tg.cancel_scope.cancel()


_node_manager: Optional[NodeManager] = None


def get_node_manager() -> NodeManager:
    assert _node_manager is not None, "Node manager has not been set."

    return _node_manager


def set_node_manager(manager: NodeManager):
    global _node_manager

    _node_manager = manager
