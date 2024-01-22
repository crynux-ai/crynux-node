from typing import Tuple

from web3 import Web3

from crynux_server.contracts import Contracts
from crynux_server.models import GpuInfo, ChainNodeStatus


async def test_node(contracts_with_tokens: Tuple[Contracts, Contracts, Contracts], tx_option):
    c1, c2, c3 = contracts_with_tokens

    node_contract_address = c1.node_contract.address
    waiter = await c1.token_contract.approve(node_contract_address, Web3.to_wei(400, "ether"), option=tx_option)
    await waiter.wait()
    waiter = await c2.token_contract.approve(node_contract_address, Web3.to_wei(400, "ether"), option=tx_option)
    await waiter.wait()
    waiter = await c3.token_contract.approve(node_contract_address, Web3.to_wei(400, "ether"), option=tx_option)
    await waiter.wait()

    gpus = [
        GpuInfo(name="NVIDIA GeForce GTX 1070 Ti", vram=8),
        GpuInfo(name="NVIDIA GeForce RTX 4060 Ti", vram=8),
        GpuInfo(name="NVIDIA GeForce RTX 4060 Ti", vram=16)
    ]

    waiter = await c1.node_contract.join(gpu_name=gpus[0].name, gpu_vram=gpus[0].vram, option=tx_option)
    await waiter.wait()
    waiter = await c2.node_contract.join(gpu_name=gpus[1].name, gpu_vram=gpus[1].vram, option=tx_option)
    await waiter.wait()
    waiter = await c3.node_contract.join(gpu_name=gpus[2].name, gpu_vram=gpus[2].vram, option=tx_option)
    await waiter.wait()

    assert (await c1.node_contract.total_nodes()) == 3
    assert (await c1.node_contract.available_nodes()) == 3

    node_addresses = await c1.node_contract.get_all_node_addresses()
    assert len(node_addresses) == 3
    assert all(c.account in node_addresses for c in contracts_with_tokens)

    available_nodes = await c1.node_contract.get_available_nodes()
    assert len(available_nodes) == 3
    assert all(c.account in available_nodes for c in contracts_with_tokens)

    available_gpus = await c1.node_contract.get_available_gpus()
    assert len(available_gpus) == 3
    assert all(gpu in available_gpus for gpu in gpus)

    for i, c in enumerate(contracts_with_tokens):
        info = await c.node_contract.get_node_info(c.account)
        assert info.status == ChainNodeStatus.AVAILABLE
        assert info.gpu.name == gpus[i].name
        assert info.gpu.vram == gpus[i].vram

    waiter = await c2.node_contract.pause(option=tx_option)
    await waiter.wait()

    assert (await c1.node_contract.available_nodes()) == 2
    assert (await c1.node_contract.total_nodes()) == 3

    available_nodes = await c1.node_contract.get_available_nodes()
    assert len(available_nodes) == 2
    assert c1.account in available_nodes
    assert c3.account in available_nodes

    available_gpus = await c1.node_contract.get_available_gpus()
    assert len(available_gpus) == 2
    assert gpus[0] in available_gpus
    assert gpus[2] in available_gpus

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
