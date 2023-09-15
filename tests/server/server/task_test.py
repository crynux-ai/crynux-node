from typing import List

from anyio import create_task_group, sleep
from fastapi.testclient import TestClient

from h_server import models
from h_server.contracts import Contracts
from h_server.models.task import PoseConfig, TaskConfig
from h_server.node_manager import NodeManager, start
from h_server.relay import Relay
from h_server.utils import get_task_data_hash, get_task_hash


async def test_get_task_stats_empty(client: TestClient):
    resp = client.get("/manager/v1/tasks")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["status"] == "waiting"
    assert resp_data["num_today"] == 0
    assert resp_data["num_total"] == 0


async def start_nodes(
    node_contracts: List[Contracts],
    managers: List[NodeManager],
):
    waits = [
        await start(c, n.node_state_manager) for c, n in zip(node_contracts, managers)
    ]
    async with create_task_group() as tg:
        for w in waits:
            tg.start_soon(w)


async def create_task(
    node_contracts: List[Contracts],
    relay: Relay,
    tx_option,
):
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
    return task.task_id


async def test_upload_task_result(
    running_client: TestClient, node_contracts, managers, relay, tx_option
):
    await start_nodes(node_contracts=node_contracts, managers=managers)
    task_id = await create_task(node_contracts=node_contracts, relay=relay, tx_option=tx_option)
    await sleep(1)

    result_file = "test.png"
    result_hash = "0x0102030405060708"
    data = {
        "hashes": [result_hash],
    }
    files = (("files", (result_file, open(result_file, "rb"), "image/png")),)
    resp = running_client.post(
        f"/manager/v1/tasks/{task_id}/result", data=data, files=files
    )
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["success"]


async def test_get_task_stats(
    running_client: TestClient, node_contracts, managers, relay, tx_option
):
    resp = running_client.get("/manager/v1/tasks")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["status"] == "stopped"
    assert resp_data["num_today"] == 0
    assert resp_data["num_total"] == 0

    await start_nodes(node_contracts=node_contracts, managers=managers)
    resp = running_client.get("/manager/v1/tasks")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["status"] == "idle"
    assert resp_data["num_today"] == 0
    assert resp_data["num_total"] == 0

    await create_task(node_contracts=node_contracts, relay=relay, tx_option=tx_option)
    await sleep(1)

    resp = running_client.get("/manager/v1/tasks")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["status"] == "running"
    assert resp_data["num_today"] == 0
    assert resp_data["num_total"] == 0
