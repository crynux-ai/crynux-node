import pytest
from eth_account import Account
from web3 import Web3

from crynux_server.contracts import Contracts


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
def provider():
    from web3.providers.eth_tester import AsyncEthereumTesterProvider

    provider = AsyncEthereumTesterProvider()
    return provider

@pytest.fixture(scope="module")
async def root_contracts(provider, tx_option, privkeys):

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

    try:
        yield c0
    finally:
        await c0.close()



@pytest.fixture(scope="module")
async def contracts_with_tokens(provider, root_contracts: Contracts, tx_option, privkeys):
    node_contract_address = root_contracts.node_contract.address
    task_contract_address = root_contracts.task_contract.address
    qos_contract_address = root_contracts.task_contract.address
    task_queue_contract_address = root_contracts.task_queue_contract.address
    netstats_contract_address = root_contracts.netstats_contract.address

    cs = []
    for privkey in privkeys:
        contracts = Contracts(provider=provider, privkey=privkey)
        await contracts.init(
            node_contract_address=node_contract_address,
            task_contract_address=task_contract_address,
            qos_contract_address=qos_contract_address,
            task_queue_contract_address=task_queue_contract_address,
            netstats_contract_address=netstats_contract_address,
            option=tx_option,
        )
        cs.append(contracts)
    
    try:
        yield tuple(cs)
    finally:
        for c in cs:
            await c.close()

