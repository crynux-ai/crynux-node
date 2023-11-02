import pytest
from typing import List

from h_server.contracts import Contracts, TxOption, set_contracts
from eth_account import Account
from web3 import Web3


@pytest.fixture
def tx_option():
    return {}


@pytest.fixture
def privkey():
    return "0xa627246a109551432ac5db6535566af34fdddfaa11df17b8afd53eb987e209a2"

@pytest.fixture
async def root_contracts(tx_option, privkey):
    from web3.providers.eth_tester import AsyncEthereumTesterProvider

    provider = AsyncEthereumTesterProvider()
    c0 = Contracts(provider=provider, default_account_index=0)

    await c0.init(option=tx_option)

    waiter = await c0.node_contract.update_task_contract_address(
        c0.task_contract.address, option=tx_option
    )
    await waiter.wait()

    provider.ethereum_tester.add_account(privkey)
    account = Account.from_key(privkey)
    amount = Web3.to_wei(1000, "ether")
    await c0.transfer(account.address, amount, option=tx_option)

    return c0


@pytest.fixture
async def node_contracts(
    root_contracts: Contracts, tx_option: TxOption, privkey: str
):
    token_contract_address = root_contracts.token_contract.address
    node_contract_address = root_contracts.node_contract.address
    task_contract_address = root_contracts.task_contract.address

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

    set_contracts(contracts)
    return contracts
