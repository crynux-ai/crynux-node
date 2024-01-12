import secrets
import time
from typing import Tuple

from anyio import create_task_group, create_memory_object_stream
import pytest
from web3 import Web3

from h_server.models import ChainNodeStatus, TaskType
from h_server.contracts import Contracts, TxRevertedError
from h_server.watcher import EventWatcher


@pytest.fixture(scope="module")
async def contracts_for_task(
    contracts_with_tokens: Tuple[Contracts, Contracts, Contracts], tx_option
):
    c1, c2, c3 = contracts_with_tokens

    node_contract_address = c1.node_contract.address
    task_contract_address = c1.task_contract.address
    task_amount = Web3.to_wei(400, "ether")
    if (await c1.token_contract.allowance(task_contract_address)) < task_amount:
        waiter = await c1.token_contract.approve(
            task_contract_address, task_amount, option=tx_option
        )
        await waiter.wait()
    if (await c2.token_contract.allowance(task_contract_address)) < task_amount:
        waiter = await c2.token_contract.approve(
            task_contract_address, task_amount, option=tx_option
        )
        await waiter.wait()
    if (await c3.token_contract.allowance(task_contract_address)) < task_amount:
        waiter = await c3.token_contract.approve(
            task_contract_address, task_amount, option=tx_option
        )
        await waiter.wait()

    node_amount = Web3.to_wei(400, "ether")
    if (await c1.token_contract.allowance(node_contract_address)) < node_amount:
        waiter = await c1.token_contract.approve(
            node_contract_address, node_amount, option=tx_option
        )
        await waiter.wait()
    if (await c2.token_contract.allowance(node_contract_address)) < node_amount:
        waiter = await c2.token_contract.approve(
            node_contract_address, node_amount, option=tx_option
        )
        await waiter.wait()
    if (await c3.token_contract.allowance(node_contract_address)) < node_amount:
        waiter = await c3.token_contract.approve(
            node_contract_address, node_amount, option=tx_option
        )
        await waiter.wait()

    try:
        waiter = await c1.node_contract.join(
            gpu_name="NVIDIA GeForce GTX 1070 Ti", gpu_vram=8, option=tx_option
        )
        await waiter.wait()
    except TxRevertedError as e:
        pass
    try:
        waiter = await c2.node_contract.join(
            gpu_name="NVIDIA GeForce RTX 4060 Ti", gpu_vram=8, option=tx_option
        )
        await waiter.wait()
    except TxRevertedError as e:
        pass
    try:
        waiter = await c3.node_contract.join(
            gpu_name="NVIDIA GeForce RTX 4060 Ti", gpu_vram=16, option=tx_option
        )
        await waiter.wait()
    except TxRevertedError as e:
        pass
    try:
        yield c1, c2, c3
    finally:
        waiter = await c1.node_contract.quit(option=tx_option)
        await waiter.wait()
        waiter = await c2.node_contract.quit(option=tx_option)
        await waiter.wait()
        waiter = await c3.node_contract.quit(option=tx_option)
        await waiter.wait()


async def test_task(
    contracts_for_task: Tuple[Contracts, Contracts, Contracts], tx_option
):
    c1, c2, c3 = contracts_for_task
    contracts_map = {c.account: c for c in contracts_for_task}

    task_hash = Web3.keccak(text="task_hash")
    data_hash = Web3.keccak(text="data_hash")

    waiter = await c1.task_contract.create_task(
        task_type=TaskType.SD,
        task_hash=task_hash,
        data_hash=data_hash,
        vram_limit=8,
        option=tx_option,
    )
    receipt = await waiter.wait()

    events = await c1.task_contract.get_events(
        "TaskCreated",
        from_block=receipt["blockNumber"],
    )
    assert len(events) == 3
    event = events[0]
    task_id = event["args"]["taskId"]
    assert event["args"]["creator"] == c1.account
    assert event["args"]["taskHash"] == task_hash
    assert event["args"]["dataHash"] == data_hash

    selected_nodes = [event["args"]["selectedNode"] for event in events]
    assert all(c.account in selected_nodes for c in contracts_for_task)

    round_map = {
        event["args"]["selectedNode"]: event["args"]["round"] for event in events
    }

    result = bytes.fromhex("0102030405060708")

    for c in contracts_for_task:
        nonce = secrets.token_bytes(32)
        commitment = Web3.solidity_keccak(["bytes", "bytes32"], [result, nonce])

        waiter = await c.task_contract.submit_task_result_commitment(
            task_id, round_map[c.account], commitment, nonce, option=tx_option
        )
        receipt = await waiter.wait()
    events = await c1.task_contract.get_events(
        "TaskResultCommitmentsReady", from_block=receipt["blockNumber"]
    )
    assert len(events) == 1
    event = events[0]
    assert event["args"]["taskId"] == task_id

    from_block = receipt["blockNumber"]
    for c in contracts_for_task:
        waiter = await c.task_contract.disclose_task_result(
            task_id=task_id, round=round_map[c.account], result=result, option=tx_option
        )
        receipt = await waiter.wait()
    to_block = receipt["blockNumber"]
    events = await c1.task_contract.get_events(
        "TaskSuccess", from_block=from_block, to_block=to_block
    )
    assert len(events) == 1
    event = events[0]
    assert event["args"]["taskId"] == task_id
    assert event["args"]["result"] == result

    result_account = event["args"]["resultNode"]
    result_node = contracts_map[result_account]

    task = await result_node.task_contract.get_task(task_id=task_id)
    assert task.result_node == result_account

    waiter = await result_node.task_contract.report_results_uploaded(
        task_id=task_id, round=round_map[result_account], option=tx_option
    )
    await waiter.wait()

    for c in contracts_for_task:
        task_id = await c.task_contract.get_node_task(c.account)
        assert task_id == 0
        status = await c.node_contract.get_node_status(c.account)
        assert status == ChainNodeStatus.AVAILABLE


async def test_task_with_event_watcher(
    contracts_for_task: Tuple[Contracts, Contracts, Contracts], tx_option
):
    c1, c2, c3 = contracts_for_task
    contracts_map = {c.account: c for c in contracts_for_task}

    watcher = EventWatcher.from_contracts(c1)
    event_send, event_recv = create_memory_object_stream()

    async def _push_event(event):
        await event_send.send(event)

    async with create_task_group() as tg:
        tg.start_soon(watcher.start)

        task_hash = Web3.keccak(text="task_hash")
        data_hash = Web3.keccak(text="data_hash")

        watcher.watch_event(
            "task", "TaskCreated", _push_event, filter_args={"creator": c1.account}
        )
        waiter = await c1.task_contract.create_task(
            task_type=TaskType.SD,
            task_hash=task_hash,
            data_hash=data_hash,
            vram_limit=8,
            option=tx_option,
        )
        await waiter.wait()

        task_id: int = -1
        selected_nodes = []
        round_map = {}
        for _ in range(3):
            event = await event_recv.receive()
            if task_id == -1:
                task_id = event["args"]["taskId"]
            else:
                assert task_id == event["args"]["taskId"]
            assert event["args"]["creator"] == c1.account
            assert event["args"]["taskHash"] == task_hash
            assert event["args"]["dataHash"] == data_hash

            selected_node = event["args"]["selectedNode"]
            round = event["args"]["round"]
            selected_nodes.append(event["args"]["selectedNode"])
            round_map[selected_node] = round

        assert all(c.account in selected_nodes for c in contracts_for_task)

        result = bytes.fromhex("0102030405060708")

        watcher.watch_event(
            "task",
            "TaskResultCommitmentsReady",
            _push_event,
            filter_args={"taskId": task_id},
        )
        for c in contracts_for_task:
            nonce = secrets.token_bytes(32)
            commitment = Web3.solidity_keccak(["bytes", "bytes32"], [result, nonce])

            waiter = await c.task_contract.submit_task_result_commitment(
                task_id, round_map[c.account], commitment, nonce, option=tx_option
            )
            await waiter.wait()

        event = await event_recv.receive()
        assert event["args"]["taskId"] == task_id

        watcher.watch_event(
            "task", "TaskSuccess", _push_event, filter_args={"taskId": task_id}
        )
        for c in contracts_for_task:
            waiter = await c.task_contract.disclose_task_result(
                task_id=task_id,
                round=round_map[c.account],
                result=result,
                option=tx_option,
            )
            await waiter.wait()

        event = await event_recv.receive()
        assert event["args"]["taskId"] == task_id
        assert event["args"]["result"] == result

        result_account = event["args"]["resultNode"]
        result_node = contracts_map[result_account]

        task = await result_node.task_contract.get_task(task_id=task_id)
        assert task.result_node == result_account

        waiter = await result_node.task_contract.report_results_uploaded(
            task_id=task_id, round=round_map[result_account], option=tx_option
        )
        await waiter.wait()

        for c in contracts_for_task:
            task_id = await c.task_contract.get_node_task(c.account)
            assert task_id == 0
            status = await c.node_contract.get_node_status(c.account)
            assert status == ChainNodeStatus.AVAILABLE

        await event_recv.aclose()
        await event_send.aclose()
        watcher.stop()


async def test_fail_task_creation(
    contracts_for_task: Tuple[Contracts, Contracts, Contracts], tx_option
):
    c1, c2, c3 = contracts_for_task

    task_hash = Web3.keccak(text="task_hash")
    data_hash = Web3.keccak(text="data_hash")

    with pytest.raises(Exception) as e:
        waiter = await c1.task_contract.create_task(
            task_type=TaskType.SD,
            task_hash=task_hash,
            data_hash=data_hash,
            vram_limit=16,
            option=tx_option,
        )
        await waiter.wait()

    assert "No kind of gpu vram meets condition" in str(e.value)

    with pytest.raises(Exception) as e:
        waiter = await c1.task_contract.create_task(
            task_type=TaskType.LLM,
            task_hash=task_hash,
            data_hash=data_hash,
            vram_limit=8,
            option=tx_option,
        )
        await waiter.wait()

    assert "No kind of gpu id meets condition" in str(e.value)


async def test_get_task(
    contracts_for_task: Tuple[Contracts, Contracts, Contracts], tx_option
):
    ts = int(time.time())
    
    c1, c2, c3 = contracts_for_task

    task_hash = Web3.keccak(text="task_hash")
    data_hash = Web3.keccak(text="data_hash")

    waiter = await c1.task_contract.create_task(
        task_type=TaskType.SD,
        task_hash=task_hash,
        data_hash=data_hash,
        vram_limit=8,
        option=tx_option,
    )
    receipt = await waiter.wait()

    events = await c1.task_contract.get_events(
        "TaskCreated",
        from_block=receipt["blockNumber"],
    )
    assert len(events) == 3
    event = events[0]
    task_id = event["args"]["taskId"]

    task = await c1.task_contract.get_task(task_id=task_id)
    assert task.id == task_id
    assert task.task_type == TaskType.SD
    assert task.task_hash == task_hash
    assert task.data_hash == data_hash
    assert task.vram_limit == 8
    assert not task.is_success
    assert len(task.selected_nodes) == 3
    assert all(c.account in task.selected_nodes for c in contracts_for_task)
    assert len(task.commitments) == 3
    assert all(c == bytes([0] * 32) for c in task.commitments)
    assert len(task.nonces) == 3
    assert all(n == bytes([0] * 32) for n in task.nonces)
    assert len(task.results) == 3
    assert all(r == b"" for r in task.results)
    assert len(task.result_disclosed_rounds) == 0
    assert task.result_node == "0x" + bytes([0] * 20).hex()
    assert not task.aborted
    assert task.timeout >= ts + 900
