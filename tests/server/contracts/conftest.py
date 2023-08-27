from typing import Tuple

import pytest

from h_server.contracts import Contracts


@pytest.fixture(scope="module")
def tx_option():
    # return {}
    return {"chainId": 42, "gas": 4294967, "gasPrice": 1}


@pytest.fixture(scope="module")
async def root_contracts(anyio_backend, tx_option):
    # from web3.providers.eth_tester import AsyncEthereumTesterProvider

    # c0 = Contracts(provider=AsyncEthereumTesterProvider(), default_account_index=0)

    # await c0.init(option=tx_option)

    # await c0.node_contract.update_task_contract_address(
    #     c0.task_contract.address, option=tx_option
    # )

    # return c0

    c0 = Contracts(
        provider_path="https://block-node.crynux.ai/rpc",
        privkey="0x420fcabfd5dbb55215490693062e6e530840c64de837d071f0d9da21aaac861e",
    )

    token_contract_address = "0x2045334b59E72B91ee072b6971F1eAbFa496A5D7"
    node_contract_address = "0xcc0576ceEc40A9309f231d59B36A5c6e5625d6e5"
    task_contract_address = "0x81968268d3aCdCba99a677C960C2B5dFb8B38768"

    await c0.init(
        token_contract_address=token_contract_address,
        node_contract_address=node_contract_address,
        task_contract_address=task_contract_address,
        option=tx_option,
    )

    await c0.node_contract.update_task_contract_address(
        task_contract_address, option=tx_option
    )
    return c0


@pytest.fixture(scope="module")
async def contracts_with_tokens(root_contracts: Contracts, tx_option):
    from web3 import Web3

    token_contract_address = root_contracts.token_contract.address
    node_contract_address = root_contracts.node_contract.address
    task_contract_address = root_contracts.task_contract.address

    c1 = Contracts(provider=root_contracts.provider, privkey="0xa627246a109551432ac5db6535566af34fdddfaa11df17b8afd53eb987e209a2")
    await c1.init(token_contract_address, node_contract_address, task_contract_address)

    c2 = Contracts(provider=root_contracts.provider, privkey="0xb171f296622b98cbdc08dcdcb0696f738c3a22d9d367c657117cd3c8d0b71d42")
    await c2.init(token_contract_address, node_contract_address, task_contract_address)

    c3 = Contracts(provider=root_contracts.provider, privkey="0x8fb2fc9862b93b5b75cda8202f583711201e4cba5459eefe442b8c5dcc4bdab9")
    await c3.init(token_contract_address, node_contract_address, task_contract_address)

    amount = Web3.to_wei(1000, "ether")
    if (await c1.token_contract.balance_of(c1.account)) < amount:
        await root_contracts.token_contract.transfer(
            c1.account, amount, option=tx_option
        )
    if (await c2.token_contract.balance_of(c2.account)) < amount:
        await root_contracts.token_contract.transfer(
            c2.account, Web3.to_wei(1000, "ether"), option=tx_option
        )
    if (await c3.token_contract.balance_of(c3.account)) < amount:
        await root_contracts.token_contract.transfer(
            c3.account, Web3.to_wei(1000, "ether"), option=tx_option
        )

    return c1, c2, c3
