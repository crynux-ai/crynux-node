from fastapi.testclient import TestClient
from anyio import sleep


async def test_control_node(running_client: TestClient):
    while True:
        resp = running_client.get("/manager/v1/node")
        resp.raise_for_status()
        resp_data = resp.json()
        assert resp_data["tx_status"] in ["", "pending"]
        if resp_data["tx_status"] == "":
            assert resp_data["status"] in ["running", "initializing"]
            if resp_data["status"] == "running":
                break
            else:
                await sleep(1)
        else:
            await sleep(1)

    resp = running_client.post("/manager/v1/node", json={"action": "pause"})
    resp.raise_for_status()
    assert resp.json()["success"]

    resp = running_client.get("/manager/v1/node")
    while True:
        resp = running_client.get("/manager/v1/node")
        resp.raise_for_status()
        resp_data = resp.json()
        assert resp_data["tx_status"] in ["", "pending_pause"]
        if resp_data["tx_status"] == "":
            assert resp_data["status"] == "paused"
            break
        else:
            await sleep(1)

    resp = running_client.post("/manager/v1/node", json={"action": "resume"})
    resp.raise_for_status()
    assert resp.json()["success"]

    while True:
        resp = running_client.get("/manager/v1/node")
        resp.raise_for_status()
        resp_data = resp.json()
        assert resp_data["tx_status"] in ["", "pending"]
        if resp_data["tx_status"] == "":
            assert resp_data["status"] == "running"
            break
        else:
            await sleep(1)

    resp = running_client.post("/manager/v1/node", json={"action": "stop"})
    resp.raise_for_status()
    assert resp.json()["success"]
    while True:
        resp = running_client.get("/manager/v1/node")
        resp.raise_for_status()
        resp_data = resp.json()
        assert resp_data["tx_status"] in ["", "pending_stop"]
        if resp_data["tx_status"] == "":
            assert resp_data["status"] == "stopped"
            break
        else:
            await sleep(1)

    resp = running_client.post("/manager/v1/node", json={"action": "start"})
    resp.raise_for_status()
    assert resp.json()["success"]

    while True:
        resp = running_client.get("/manager/v1/node")
        resp.raise_for_status()
        resp_data = resp.json()
        assert resp_data["tx_status"] in ["", "pending"]
        if resp_data["tx_status"] == "":
            assert resp_data["status"] == "running"
            break
        else:
            await sleep(1)
