import secrets

from anyio import sleep
from fastapi.testclient import TestClient
from web3 import Web3

from h_server import models
from h_server.event_queue import get_event_queue


async def test_upload_task_result(client: TestClient):
    task_id = 1
    creator = Web3.to_checksum_address("0xd075aB490857256e6fc85d75d8315e7c9914e008")
    address = Web3.to_checksum_address("0x577887519278199ce8F8D80bAcc70fc32b48daD4")
    task_hash = "0x" + secrets.token_bytes(32).hex()
    data_hash = "0x" + secrets.token_bytes(32).hex()
    round = 1

    event = models.TaskCreated(
        task_id=task_id,
        creator=creator,
        selected_node=address,
        task_hash=task_hash,
        data_hash=data_hash,
        round=round,
    )
    queue = get_event_queue()
    await queue.put(event)

    await sleep(1)

    result_file = "test.png"
    result_hash = "0x0102030405060708"
    data = {
        "hashes": [result_hash],
    }
    files = (("files", (result_file, open(result_file, "rb"), "image/png")),)
    resp = client.post(f"/v1/tasks/{task_id}/result", data=data, files=files)
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["success"]


async def test_get_task_stats(client: TestClient):
    resp = client.get("/v1/tasks")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["status"] == "idle"
    assert resp_data["num_today"] == 0
    assert resp_data["num_total"] == 0
