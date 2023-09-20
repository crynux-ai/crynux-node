import secrets
import os
import shutil
from io import BytesIO
from typing import List

import pytest
from anyio import create_task_group
from eth_account import Account
from PIL import Image
from web3 import Web3

from h_server import models
from h_server.config import Config, TxOption, set_config
from h_server.contracts import Contracts
from h_server.event_queue import EventQueue, MemoryEventQueue
from h_server.models.task import PoseConfig, TaskConfig
from h_server.node_manager import (
    NodeManager,
    NodeStateManager,
    pause,
    resume,
    start,
    stop,
)
from h_server.node_manager.state_cache import MemoryNodeStateCache, MemoryTxStateCache
from h_server.relay import MockRelay, Relay
from h_server.task import InferenceTaskRunner, MemoryTaskStateCache, TaskSystem
from h_server.task.state_cache import TaskStateCache
from h_server.utils import get_task_data_hash, get_task_hash
from h_server.watcher import EventWatcher, MemoryBlockNumberCache


@pytest.fixture
def tx_option():
    return {}


@pytest.fixture
def privkeys():
    return [
        "0xa627246a109551432ac5db6535566af34fdddfaa11df17b8afd53eb987e209a2",
        "0xb171f296622b98cbdc08dcdcb0696f738c3a22d9d367c657117cd3c8d0b71d42",
        "0x8fb2fc9862b93b5b75cda8202f583711201e4cba5459eefe442b8c5dcc4bdab9",
    ]


@pytest.fixture
async def root_contracts(tx_option, privkeys):
    from web3.providers.eth_tester import AsyncEthereumTesterProvider

    provider = AsyncEthereumTesterProvider()
    c0 = Contracts(provider=provider, default_account_index=0)

    await c0.init(option=tx_option)

    waiter = await c0.node_contract.update_task_contract_address(
        c0.task_contract.address, option=tx_option
    )
    await waiter.wait()

    for privkey in privkeys:
        provider.ethereum_tester.add_account(privkey)
        account = Account.from_key(privkey)
        amount = Web3.to_wei(1000, "ether")
        await c0.transfer(account.address, amount, option=tx_option)

    return c0


@pytest.fixture
def config():
    test_config = Config.model_validate(
        {
            "log": {"dir": "logs", "level": "INFO"},
            "ethereum": {
                "privkey": "",
                "provider": "",
                "chain_id": None,
                "gas": None,
                "gas_price": None,
                "contract": {"token": "", "node": "", "task": ""},
            },
            "task_dir": "task",
            "db": "",
            "relay_url": "",
            "celery": {"broker": "", "backend": ""},
            "distributed": False,
            "task_config": {
                "data_dir": "build/data/workspace",
                "pretrained_models_dir": "build/data/pretrained-models",
                "controlnet_models_dir": "build/data/controlnet",
                "training_logs_dir": "build/data/training-logs",
                "inference_logs_dir": "build/data/inference-logs",
                "script_dir": "remote-lora-scripts",
                "result_url": "",
            },
        }
    )
    set_config(test_config)
    return test_config


@pytest.fixture
async def node_contracts(
    root_contracts: Contracts, tx_option: TxOption, privkeys: List[str]
):
    token_contract_address = root_contracts.token_contract.address
    node_contract_address = root_contracts.node_contract.address
    task_contract_address = root_contracts.task_contract.address

    cs = []
    for privkey in privkeys:
        contracts = Contracts(provider=root_contracts.provider, privkey=privkey)
        await contracts.init(
            token_contract_address=token_contract_address,
            node_contract_address=node_contract_address,
            task_contract_address=task_contract_address,
            option=tx_option,
        )
        amount = Web3.to_wei(1000, "ether")
        if (await contracts.token_contract.balance_of(contracts.account)) < amount:
            waiter = await root_contracts.token_contract.transfer(
                contracts.account, amount, option=tx_option
            )
            await waiter.wait()
        task_amount = Web3.to_wei(400, "ether")
        if (
            await contracts.token_contract.allowance(task_contract_address)
        ) < task_amount:
            waiter = await contracts.token_contract.approve(
                task_contract_address, task_amount, option=tx_option
            )
            await waiter.wait()
        node_amount = Web3.to_wei(400, "ether")
        if (
            await contracts.token_contract.allowance(node_contract_address)
        ) < node_amount:
            waiter = await contracts.token_contract.approve(
                node_contract_address, node_amount, option=tx_option
            )
            await waiter.wait()

        cs.append(contracts)
    return cs


@pytest.fixture
def relay():
    return MockRelay()


@pytest.fixture
async def node_managers(
    privkeys: List[str], node_contracts: List[Contracts], relay: Relay, config: Config
):
    managers = []
    new_data_dirs = []

    for i, (privkey, contracts) in enumerate(zip(privkeys, node_contracts)):
        queue = MemoryEventQueue()

        watcher = EventWatcher.from_contracts(contracts)
        block_number_cache = MemoryBlockNumberCache()
        watcher.set_blocknumber_cache(block_number_cache)

        def make_callback(queue):
            async def _push_event(event_data):
                event = models.load_event_from_contracts(event_data)
                await queue.put(event)

            return _push_event

        watcher.watch_event(
            "task",
            "TaskCreated",
            callback=make_callback(queue),
            filter_args={"selectedNode": contracts.account},
        )

        task_state_cache = MemoryTaskStateCache()
        system = TaskSystem(
            task_state_cache,
            queue=queue,
            distributed=config.distributed,
            task_name="mock_lora_inference",
        )

        assert config.task_config is not None
        local_config = config.task_config.model_copy()
        data_dir = f"build/data/workspace{i}"
        if not os.path.exists(data_dir):
            shutil.copytree(local_config.data_dir, data_dir)
        local_config.data_dir = data_dir
        new_data_dirs.append(data_dir)

        def make_runner_cls(contracts, relay, watcher, local_config):
            class _InferenceTaskRunner(InferenceTaskRunner):
                def __init__(
                    self,
                    task_id: int,
                    state_cache: TaskStateCache,
                    queue: EventQueue,
                    task_name: str,
                    distributed: bool,
                ) -> None:
                    super().__init__(
                        task_id,
                        state_cache,
                        queue,
                        task_name,
                        distributed,
                        contracts,
                        relay,
                        watcher,
                        local_config,
                    )

            return _InferenceTaskRunner

        system.set_runner_cls(make_runner_cls(contracts, relay, watcher, local_config))

        state_manager = NodeStateManager(
            node_state_cache_cls=MemoryNodeStateCache,
            tx_state_cache_cls=MemoryTxStateCache,
        )
        # set init state to stopped to bypass prefetch stage
        await state_manager.set_node_state(models.NodeStatus.Stopped)

        manager = NodeManager(
            config=config,
            node_state_manager=state_manager,
            privkey=privkey,
            event_queue=queue,
            contracts=contracts,
            relay=relay,
            watcher=watcher,
            task_system=system,
            restart_delay=0,  # throw the error instead of retry
        )
        managers.append(manager)

    try:
        yield managers
    finally:
        for data_dir in new_data_dirs:
            if os.path.exists(data_dir):
                shutil.rmtree(data_dir)


async def test_node_manager(
    node_managers: List[NodeManager],
    node_contracts: List[Contracts],
    relay: Relay,
    tx_option,
):
    async with create_task_group() as tg:
        for n in node_managers:
            tg.start_soon(n.run)

        waits = [
            await start(c, n.node_state_manager, option=tx_option)
            for c, n in zip(node_contracts, node_managers)
        ]
        for n in node_managers:
            assert (
                await n.node_state_manager.get_tx_state()
            ).status == models.TxStatus.Pending
        async with create_task_group() as sub_tg:
            for w in waits:
                sub_tg.start_soon(w)

        for n in node_managers:
            assert (
                await n.node_state_manager.get_node_state()
            ).status == models.NodeStatus.Running

        task = models.RelayTaskInput(
            task_id=1,
            base_model="stable-diffusion-v1-5-pruned",
            prompt="a mame_cat lying under the window, in anime sketch style, red lips, blush, black eyes, dashed outline, brown pencil outline",
            lora_model="f4fab20c-4694-430e-8937-22cdb713da9",
            task_config=TaskConfig(
                image_width=512,
                image_height=512,
                lora_weight=100,
                num_images=1,
                seed=255728798,
                steps=40,
            ),
            pose=PoseConfig(data_url="", pose_weight=100, preprocess=False),
        )

        task_hash = get_task_hash(task.task_config)
        data_hash = get_task_data_hash(
            base_model=task.base_model,
            lora_model=task.lora_model,
            prompt=task.prompt,
            pose=task.pose,
        )
        await relay.create_task(task=task)
        waiter = await node_contracts[0].task_contract.create_task(
            task_hash=task_hash, data_hash=data_hash, option=tx_option
        )
        await waiter.wait()

        with BytesIO() as dst:
            await relay.get_result(task_id=1, image_num=0, dst=dst)
            dst.seek(0)
            img = Image.open(dst)
            assert img.width == 512
            assert img.height == 512

        waits = [
            await pause(c, n.node_state_manager, option=tx_option)
            for c, n in zip(node_contracts, node_managers)
        ]
        for n in node_managers:
            assert (
                await n.node_state_manager.get_tx_state()
            ).status == models.TxStatus.Pending
        async with create_task_group() as sub_tg:
            for w in waits:
                sub_tg.start_soon(w)

        for n in node_managers:
            assert (
                await n.node_state_manager.get_node_state()
            ).status == models.NodeStatus.Paused

        waits = [
            await resume(c, n.node_state_manager, option=tx_option)
            for c, n in zip(node_contracts, node_managers)
        ]
        for n in node_managers:
            assert (
                await n.node_state_manager.get_tx_state()
            ).status == models.TxStatus.Pending
        async with create_task_group() as sub_tg:
            for w in waits:
                sub_tg.start_soon(w)

        for n in node_managers:
            assert (
                await n.node_state_manager.get_node_state()
            ).status == models.NodeStatus.Running

        waits = [
            await stop(c, n.node_state_manager, option=tx_option)
            for c, n in zip(node_contracts, node_managers)
        ]
        for n in node_managers:
            assert (
                await n.node_state_manager.get_tx_state()
            ).status == models.TxStatus.Pending
        async with create_task_group() as sub_tg:
            for w in waits:
                sub_tg.start_soon(w)

        for n in node_managers:
            assert (
                await n.node_state_manager.get_node_state()
            ).status == models.NodeStatus.Stopped

        for n in node_managers:
            await n.finish()
        tg.cancel_scope.cancel()


async def partial_run_task(
    config: Config,
    node_managers: List[NodeManager],
    node_contracts: List[Contracts],
    relay: Relay,
    tx_option,
    stage: int,
):
    # start nodes
    waits = [
        await start(c, n.node_state_manager, option=tx_option)
        for c, n in zip(node_contracts, node_managers)
    ]
    async with create_task_group() as sub_tg:
        for w in waits:
            sub_tg.start_soon(w)

    for n in node_managers:
        assert (
            await n.node_state_manager.get_node_state()
        ).status == models.NodeStatus.Running

    # create task
    task = models.RelayTaskInput(
        task_id=1,
        base_model="stable-diffusion-v1-5-pruned",
        prompt="a mame_cat lying under the window, in anime sketch style, red lips, blush, black eyes, dashed outline, brown pencil outline",
        lora_model="f4fab20c-4694-430e-8937-22cdb713da9",
        task_config=TaskConfig(
            image_width=512,
            image_height=512,
            lora_weight=100,
            num_images=1,
            seed=255728798,
            steps=40,
        ),
        pose=PoseConfig(data_url="", pose_weight=100, preprocess=False),
    )

    task_hash = get_task_hash(task.task_config)
    data_hash = get_task_data_hash(
        base_model=task.base_model,
        lora_model=task.lora_model,
        prompt=task.prompt,
        pose=task.pose,
    )
    waiter = await node_contracts[0].task_contract.create_task(
        task_hash=task_hash, data_hash=data_hash, option=tx_option
    )
    receipt = await waiter.wait()

    events = await node_contracts[0].task_contract.get_events(
        "TaskCreated",
        from_block=receipt["blockNumber"],
    )
    event = events[0]
    task_id = event["args"]["taskId"]
    task.task_id = task_id
    await relay.create_task(task=task)

    round_map = {
        event["args"]["selectedNode"]: event["args"]["round"] for event in events
    }

    result = bytes.fromhex("0102030405060708")
    if 1 <= stage:
        # submit task result commitment
        for c in node_contracts:
            nonce = secrets.token_bytes(32)
            commitment = Web3.solidity_keccak(["bytes", "bytes32"], [result, nonce])

            waiter = await c.task_contract.submit_task_result_commitment(
                task_id, round_map[c.account], commitment, nonce, option=tx_option
            )
            receipt = await waiter.wait()
        events = await node_contracts[0].task_contract.get_events(
            "TaskResultCommitmentsReady", from_block=receipt["blockNumber"]
        )
        assert len(events) == 1
        event = events[0]
        assert event["args"]["taskId"] == task_id
        config.last_result = "0x0102030405060708"

    if 2 <= stage:
        # disclose task
        from_block = receipt["blockNumber"]
        for c in node_contracts:
            waiter = await c.task_contract.disclose_task_result(
                task_id=task_id,
                round=round_map[c.account],
                result=result,
                option=tx_option,
            )
            receipt = await waiter.wait()
        to_block = receipt["blockNumber"]
        events = await node_contracts[0].task_contract.get_events(
            "TaskSuccess", from_block=from_block, to_block=to_block
        )
        assert len(events) == 1
        event = events[0]
        assert event["args"]["taskId"] == task_id
        assert event["args"]["result"] == result


@pytest.mark.parametrize("stage", [0, 1, 2])
async def test_node_manager_with_recover(
    config: Config,
    node_managers: List[NodeManager],
    node_contracts: List[Contracts],
    relay: Relay,
    tx_option,
    stage: int,
):
    await partial_run_task(
        config, node_managers, node_contracts, relay, tx_option, stage
    )
    async with create_task_group() as tg:
        for n in node_managers:
            tg.start_soon(n.run)

        for n in node_managers:
            assert (
                await n.node_state_manager.get_node_state()
            ).status == models.NodeStatus.Running

        with BytesIO() as dst:
            await relay.get_result(task_id=1, image_num=0, dst=dst)
            dst.seek(0)
            img = Image.open(dst)
            assert img.width == 512
            assert img.height == 512

        waits = [
            await stop(c, n.node_state_manager, option=tx_option)
            for c, n in zip(node_contracts, node_managers)
        ]
        for n in node_managers:
            assert (
                await n.node_state_manager.get_tx_state()
            ).status == models.TxStatus.Pending
        async with create_task_group() as sub_tg:
            for w in waits:
                sub_tg.start_soon(w)

        for n in node_managers:
            assert (
                await n.node_state_manager.get_node_state()
            ).status == models.NodeStatus.Stopped

        for n in node_managers:
            await n.finish()
        tg.cancel_scope.cancel()
