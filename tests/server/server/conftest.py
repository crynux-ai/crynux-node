from contextlib import asynccontextmanager
from typing import List

import pytest
from anyio import create_task_group
from eth_account import Account
from fastapi.testclient import TestClient
from web3 import Web3

from h_server import models
from h_server.config import Config, TxOption, set_config
from h_server.contracts import Contracts, set_contracts
from h_server.event_queue import EventQueue, MemoryEventQueue, set_event_queue
from h_server.node_manager import NodeManager, set_node_manager
from h_server.node_manager.state_cache import MemoryNodeStateCache
from h_server.relay import MockRelay, Relay, set_relay
from h_server.server import Server
from h_server.task import (MemoryTaskStateCache, MockTaskRunner, TaskSystem,
                           set_task_state_cache, set_task_system)
from h_server.task.state_cache import TaskStateCache
from h_server.watcher import EventWatcher, MemoryBlockNumberCache, set_watcher


@pytest.fixture(scope="module")
def tx_option():
    return {}


@pytest.fixture(scope="module")
def accounts():
    return [
        "0x577887519278199ce8F8D80bAcc70fc32b48daD4",
        "0x9229d36c82E4e1d03B086C27d704741D0c78321e",
        "0xEa1A669fd6A705d28239011A074adB3Cfd6cd82B"
    ]

@pytest.fixture(scope="module")
def privkeys():
    return [
        "0xa627246a109551432ac5db6535566af34fdddfaa11df17b8afd53eb987e209a2",
        "0xb171f296622b98cbdc08dcdcb0696f738c3a22d9d367c657117cd3c8d0b71d42",
        "0x8fb2fc9862b93b5b75cda8202f583711201e4cba5459eefe442b8c5dcc4bdab9",
    ]


@pytest.fixture(scope="module")
async def root_contracts(tx_option, privkeys):
    from web3.providers.eth_tester import AsyncEthereumTesterProvider

    provider = AsyncEthereumTesterProvider()
    c0 = Contracts(provider=provider, default_account_index=0)

    await c0.init(option=tx_option)

    await c0.node_contract.update_task_contract_address(
        c0.task_contract.address, option=tx_option
    )

    for privkey in privkeys:
        provider.ethereum_tester.add_account(privkey)
        account = Account.from_key(privkey)
        amount = Web3.to_wei(1000, "ether")
        await c0.transfer(account.address, amount, option=tx_option)

    return c0


@pytest.fixture(scope="module")
def config():
    test_config = Config.model_validate(
        {
            "log": {"dir": "logs", "level": "INFO"},
            "ethereum": {
                "privkey": "",
                "provider": "",
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


@pytest.fixture(scope="module")
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
            token_contract_address, node_contract_address, task_contract_address
        )
        amount = Web3.to_wei(1000, "ether")
        if (await contracts.token_contract.balance_of(contracts.account)) < amount:
            await root_contracts.token_contract.transfer(
                contracts.account, amount, option=tx_option
            )
        task_amount = Web3.to_wei(400, "ether")
        if (
            await contracts.token_contract.allowance(task_contract_address)
        ) < task_amount:
            await contracts.token_contract.approve(
                task_contract_address, task_amount, option=tx_option
            )
        node_amount = Web3.to_wei(400, "ether")
        if (
            await contracts.token_contract.allowance(node_contract_address)
        ) < node_amount:
            await contracts.token_contract.approve(
                node_contract_address, node_amount, option=tx_option
            )

        cs.append(contracts)
    return cs


@pytest.fixture(scope="module")
def relay():
    relay = MockRelay()
    set_relay(relay)
    return relay


@pytest.fixture(scope="function", autouse=True)
async def prepare_enviroment(
    privkeys: List[str], node_contracts: List[Contracts], relay: Relay, config: Config
):
    managers: List[NodeManager] = []

    for i, (privkey, contracts) in enumerate(zip(privkeys, node_contracts)):
        if i == 0:
            set_contracts(contracts)
        queue = MemoryEventQueue()
        if i == 0:
            set_event_queue(queue)

        watcher = EventWatcher.from_contracts(contracts)
        block_number_cache = MemoryBlockNumberCache()
        watcher.set_blocknumber_cache(block_number_cache)
        if i == 0:
            set_watcher(watcher)

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
        if i == 0:
            set_task_state_cache(task_state_cache)
            set_task_system(system)

        def make_runner_cls():
            class _MockTaskRunner(MockTaskRunner):
                def __init__(self, task_id: int, state_cache: TaskStateCache, queue: EventQueue, task_name: str, distributed: bool):
                    super().__init__(task_id, state_cache, queue, task_name, distributed)

            return _MockTaskRunner

        system.set_runner_cls(make_runner_cls())

        manager = NodeManager(
            config=config,
            node_state_cache_cls=MemoryNodeStateCache,
            privkey=privkey,
            event_queue=queue,
            contracts=contracts,
            relay=relay,
            watcher=watcher,
            task_system=system,
        )
        if i == 0:
            set_node_manager(manager)
        managers.append(manager)

    @asynccontextmanager
    async def context():
        async with create_task_group() as tg:
            for manager in managers:
                tg.start_soon(manager.run)
            try:
                yield
            finally:
                for manager in managers:
                    await manager.finish()
                tg.cancel_scope.cancel()

    async with context():
        yield

@pytest.fixture(scope="module")
def client():
    return TestClient(Server().app)
