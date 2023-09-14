import pytest
from eth_account import Account
from web3 import Web3

from h_server.contracts import Contracts


@pytest.fixture(scope="module")
def tx_option():
    return {}
    # return {"chainId": 42, "gas": 4294967, "gasPrice": 1}

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


@pytest.fixture(scope="module")
async def contracts_with_tokens(root_contracts: Contracts, tx_option, privkeys):
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
            waiter = await root_contracts.token_contract.transfer(
                contracts.account, amount, option=tx_option
            )
            await waiter.wait()
        cs.append(contracts)
    return tuple(cs)
