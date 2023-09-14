from typing import Tuple

from web3 import Web3

from h_server.contracts import Contracts


async def test_node(contracts_with_tokens: Tuple[Contracts, Contracts, Contracts], tx_option):
    c1, c2, c3 = contracts_with_tokens

    node_contract_address = c1.node_contract.address
    waiter = await c1.token_contract.approve(node_contract_address, Web3.to_wei(400, "ether"), option=tx_option)
    await waiter.wait()
    waiter = await c2.token_contract.approve(node_contract_address, Web3.to_wei(400, "ether"), option=tx_option)
    await waiter.wait()
    waiter = await c3.token_contract.approve(node_contract_address, Web3.to_wei(400, "ether"), option=tx_option)
    await waiter.wait()

    waiter = await c1.node_contract.join(option=tx_option)
    await waiter.wait()
    waiter = await c2.node_contract.join(option=tx_option)
    await waiter.wait()
    waiter = await c3.node_contract.join(option=tx_option)
    await waiter.wait()

    assert (await c1.node_contract.total_nodes()) == 3
    assert (await c1.node_contract.available_nodes()) == 3

    waiter = await c2.node_contract.pause(option=tx_option)
    await waiter.wait()

    assert (await c1.node_contract.available_nodes()) == 2
    assert (await c1.node_contract.total_nodes()) == 3

    waiter = await c2.node_contract.resume(option=tx_option)
    await waiter.wait()

    assert (await c1.node_contract.available_nodes()) == 3
    assert (await c1.node_contract.total_nodes()) == 3

    waiter = await c3.node_contract.quit(option=tx_option)
    await waiter.wait()
    waiter = await c2.node_contract.quit(option=tx_option)
    await waiter.wait()
    waiter = await c1.node_contract.quit(option=tx_option)
    await waiter.wait()

    assert (await c1.node_contract.available_nodes()) == 0
    assert (await c1.node_contract.total_nodes()) == 0
