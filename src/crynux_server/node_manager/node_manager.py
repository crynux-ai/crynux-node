from __future__ import annotations

from datetime import datetime
import json
import logging
import os
from typing import List, Optional, Type, cast

from anyio import (Event, TASK_STATUS_IGNORED, create_task_group, fail_after,
                   get_cancelled_exc_class, move_on_after, to_thread)
from anyio.abc import TaskGroup, TaskStatus
from web3 import Web3
from web3.types import EventData
from tenacity import AsyncRetrying, before_sleep_log, wait_fixed

from crynux_server import models
from crynux_server.config import Config, wait_privkey
from crynux_server.contracts import Contracts, set_contracts
from crynux_server.event_queue import DbEventQueue, EventQueue, set_event_queue
from crynux_server.relay import Relay, WebRelay, set_relay
from crynux_server.task import (DbTaskStateCache, InferenceTaskRunner,
                           TaskStateCache, TaskSystem, set_task_state_cache,
                           set_task_system)
from crynux_server.watcher import (BlockNumberCache, DbBlockNumberCache,
                              EventWatcher, set_watcher)

from .state_cache import (DbNodeStateCache, DbTxStateCache, ManagerStateCache,
                          StateCache, set_manager_state_cache)
from .state_manager import NodeStateManager, set_node_state_manager

_logger = logging.getLogger(__name__)


async def _make_contracts(
    privkey: str,
    provider: str,
    token_contract_address: str,
    node_contract_address: str,
    task_contract_address: str,
    qos_contract_address: Optional[str],
    task_queue_contract_address: Optional[str],
    netstats_contract_address: Optional[str],
) -> Contracts:
    contracts = Contracts(provider_path=provider, privkey=privkey)
    await contracts.init(
        token_contract_address=token_contract_address,
        node_contract_address=node_contract_address,
        task_contract_address=task_contract_address,
        qos_contract_address=qos_contract_address,
        task_queue_contract_address=task_queue_contract_address,
        netstats_contract_address=netstats_contract_address
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
    watcher = EventWatcher.from_contracts(
        contracts
    )

    block_cache = block_number_cache_cls()
    watcher.set_blocknumber_cache(block_cache)

    async def _push_event(event_data: EventData):
        event = models.load_event_from_contracts(event_data)
        await queue.put(event)

    watcher.watch_event(
        "task",
        "TaskStarted",
        callback=_push_event,
        filter_args={"selectedNode": contracts.account},
    )
    set_watcher(watcher)
    return watcher


def _make_task_system(
    queue: EventQueue, distributed: bool, retry: bool, task_state_cache_cls: Type[TaskStateCache]
) -> TaskSystem:
    cache = task_state_cache_cls()
    set_task_state_cache(cache)

    system = TaskSystem(state_cache=cache, queue=queue, distributed=distributed, retry=retry)
    system.set_runner_cls(runner_cls=InferenceTaskRunner)

    set_task_system(system)
    return system


def _make_node_state_manager(
    state_cache: ManagerStateCache,
    contracts: Contracts,
):
    state_manager = NodeStateManager(
        state_cache=state_cache,
        contracts=contracts,
    )
    set_node_state_manager(state_manager)
    return state_manager


class NodeManager(object):
    def __init__(
        self,
        config: Config,
        gpu_name: str,
        gpu_vram: int,
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
        retry: bool = True,
        retry_delay: float = 30,
    ) -> None:
        self.config = config
        self.gpu_name = gpu_name
        self.gpu_vram = gpu_vram

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

        self._retry = retry
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
                if self.config.headless:
                    assert (
                        len(self.config.ethereum.privkey) > 0
                    ), "In headless mode, you must provide private key in config file before starting node."
                    self._privkey = self.config.ethereum.privkey
                else:
                    self._privkey = await wait_privkey()

            if self._contracts is None:
                self._contracts = await _make_contracts(
                    privkey=self._privkey,
                    provider=self.config.ethereum.provider,
                    token_contract_address=self.config.ethereum.contract.token,
                    node_contract_address=self.config.ethereum.contract.node,
                    task_contract_address=self.config.ethereum.contract.task,
                    qos_contract_address=self.config.ethereum.contract.qos,
                    task_queue_contract_address=self.config.ethereum.contract.task_queue,
                    netstats_contract_address=self.config.ethereum.contract.netstats,
                )
            if self._relay is None:
                self._relay = _make_relay(self._privkey, self.config.relay_url)

        if self._node_state_manager is None:
            self._node_state_manager = _make_node_state_manager(
                state_cache=self.state_cache,
                contracts=self._contracts,
            )

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
                    retry=self._retry,
                    task_state_cache_cls=self.task_state_cache_cls,
                )
        _logger.info("Node manager components initializing complete.")

    async def _init(self):
        _logger.info("Initialize node manager")
        await self.state_cache.set_node_state(models.NodeStatus.Init)
        # clear tx error when restart
        await self.state_cache.set_tx_state(models.TxStatus.Success)

        if not self.config.distributed:

            ### Prefetech ###
            from crynux_worker.models import ModelConfig, ProxyConfig
            from crynux_worker.prefetch import prefetch
            from crynux_worker.inference import inference

            assert (
                self.config.task_config is not None
            ), "Task config is None in non-distributed version"

            if (
                self.config.task_config is not None
                and self.config.task_config.preloaded_models is not None
            ):
                preload_models = self.config.task_config.preloaded_models.model_dump()
                base_models: List[ModelConfig] | None = preload_models.get("base", None)
                controlnet_models: List[ModelConfig] | None = preload_models.get(
                    "controlnet", None
                )
                vae_models: List[ModelConfig] | None = preload_models.get("vae", None)
            else:
                base_models = None
                controlnet_models = None
                vae_models = None

            if (
                self.config.task_config is not None
                and self.config.task_config.proxy is not None
            ):
                proxy = self.config.task_config.proxy.model_dump()
                proxy = cast(ProxyConfig, proxy)
            else:
                proxy = None

            await to_thread.run_sync(
                prefetch,
                self.config.task_config.hf_cache_dir,
                self.config.task_config.external_cache_dir,
                self.config.task_config.script_dir,
                base_models,
                controlnet_models,
                vae_models,
                proxy,
                cancellable=True,
            )


            ### Inference ###
            prompt = (
                "a realistic photo of an old man sitting on a brown chair, "
                "on the seaside, with blue sky and white clouds, a dog is lying "
                "under his legs, masterpiece, high resolution"
            )
            sd_inference_args = {
                "base_model": "runwayml/stable-diffusion-v1-5",
                "prompt": prompt,
                "negative_prompt": "",
                "task_config": {
                    "num_images": 3,
                    "safety_checker": False,
                    "cfg": 7,
                    "seed": 99975892,
                    "steps": 40
                }
            }
            current_ts = int(datetime.now().timestamp())
            try:
                with fail_after(300):
                    await to_thread.run_sync(
                        inference,
                        json.dumps(sd_inference_args),
                        os.path.join(self.config.task_config.output_dir, f"_sd_init_{current_ts}"),
                        self.config.task_config.hf_cache_dir,
                        self.config.task_config.external_cache_dir,
                        self.config.task_config.script_dir,
                        base_models,
                        controlnet_models,
                        vae_models,
                        proxy,
                        cancellable=True,
                    )
            except TimeoutError as e:
                msg = "The initial inference task is timeout (5 min). Maybe your device does not meet the lowest hardware requirements"
                raise ValueError(msg) from e
            # TODO: validate image similarity.

        _logger.info("Node manager initializing complete.")

    async def _recover(self):
        assert self._contracts is not None
        assert self._task_system is not None
        assert self._watcher is not None

        # only recover when watcher hasn't started
        blocknumber_cache = self._watcher.get_blocknumber_cache()
        if blocknumber_cache is not None and await blocknumber_cache.get() > 0:
            return

        task_id = await self._contracts.task_contract.get_node_task(
            self._contracts.account
        )
        if task_id == 0:
            return

        task = await self._contracts.task_contract.get_task(task_id=task_id)
        round = task.selected_nodes.index(self._contracts.account)
        state = models.TaskState(
            task_id=task_id, round=round, timeout=task.timeout, status=models.TaskStatus.Pending
        )

        events = []
        # task created
        event = models.TaskStarted(
            task_id=task_id,
            task_type=task.task_type,
            creator=Web3.to_checksum_address(task.creator),
            selected_node=self._contracts.account,
            task_hash=Web3.to_hex(task.task_hash),
            data_hash=Web3.to_hex(task.data_hash),
            round=round,
        )
        events.append(event)

        # has submitted result commitment
        if round < len(task.commitments) and task.commitments[round] != bytes([0] * 32):
            # has reported error, skip the task
            err_commitment = bytes([0] * 31 + [1])
            if task.commitments[round] == err_commitment:
                return

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
            _logger.debug(f"Recover event from chain {event}")
        await self._task_system.state_cache.dump(state)
        _logger.debug(f"Recover task state {state}")

    async def _sync_state(self):

        async def _inner():
            assert self._node_state_manager is not None
            try:
                await self._node_state_manager.start_sync()
            except Exception as e:
                _logger.exception(e)
                _logger.error("Cannot sync node state from chain")
                with fail_after(5, shield=True):
                    await self.state_cache.set_node_state(
                        status=models.NodeStatus.Error,
                        message="Node manager running error: cannot sync node state from chain."
                    )
                raise
        
        if self._retry:
            async for attemp in AsyncRetrying(
                wait=wait_fixed(self._retry_delay),
                before_sleep=before_sleep_log(_logger, logging.ERROR, exc_info=True),
                reraise=True,
            ):
                with attemp:
                    await _inner()
        else:
            await _inner()

    async def _watch_events(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED):

        async def _inner(first_call) -> None:
            assert self._watcher is not None
            try:
                if first_call:
                    await self._watcher.start(task_status=task_status)
                else:
                    await self._watcher.start()
            except Exception as e:
                _logger.exception(e)
                _logger.error("Cannot watch events from chain")
                with fail_after(5, shield=True):
                    await self.state_cache.set_node_state(
                        status=models.NodeStatus.Error,
                        message="Node manager running error: cannot watch events from chain."
                    )
                raise

        first_call = True

        if self._retry:
            async for attemp in AsyncRetrying(
                wait=wait_fixed(self._retry_delay),
                before_sleep=before_sleep_log(_logger, logging.ERROR, exc_info=True),
                reraise=True,
            ):
                with attemp:
                    try:
                        await _inner(first_call)
                    finally:
                        first_call = False
        else:
            await _inner(first_call)

    async def _run(self, prefetch: bool = True):
        assert self._tg is None, "Node manager is running."

        try:
            async with create_task_group() as tg:
                self._tg = tg
                try:
                    async with create_task_group() as init_tg:
                        init_tg.start_soon(self._init_components)
                        if prefetch:
                            init_tg.start_soon(self._init)
                except get_cancelled_exc_class():
                    raise
                except Exception as e:
                    _logger.exception(e)
                    msg = f"Node manager init error: {str(e)}"
                    _logger.error(msg)
                    with fail_after(5, shield=True):
                        await self.state_cache.set_node_state(
                            models.NodeStatus.Error, msg
                        )
                    await self.finish()
                    return

                await self._recover()

                assert self._task_system is not None
                tg.start_soon(self._task_system.start)

                if not self.config.headless:
                    tg.start_soon(self._sync_state)

                # wait the event watcher to start first and then join the network sequentially
                # because the node may be selected to execute one task in the same tx of join,
                # start watcher after the joining operation will cause missing the TaskStarted event.
                await tg.start(self._watch_events)

                assert self._node_state_manager is not None
                try:
                    await self._node_state_manager.try_start(self.gpu_name, self.gpu_vram)
                except Exception as e:
                    if self.config.headless:
                        raise e
                    else:
                        _logger.warn(e)
                        _logger.info("Cannot auto join the network")
        finally:
            self._tg = None

    async def run(self, prefetch: bool = True):
        assert self._tg is None, "Node manager is running."

        try:
            await self._run(prefetch=prefetch)
        except get_cancelled_exc_class():
            raise
        except Exception as e:
            _logger.exception(e)
            msg = f"Node manager running error: {str(e)}"
            _logger.error(msg)
            with fail_after(5, shield=True):
                await self.state_cache.set_node_state(models.NodeStatus.Error, msg)
            await self.finish()
            if self.config.headless:
                raise

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
            with move_on_after(10, shield=True):
                await self._node_state_manager.try_stop()
            if not self.config.headless:
                self._node_state_manager.stop_sync()
            self._node_state_manager = None
        if self._contracts is not None:
            await self._contracts.close()
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
