from fastapi.testclient import TestClient
from anyio import sleep


async def test_control_node(client: TestClient):
    while True:
        resp = client.get("/manager/manager/v1/node")
        resp.raise_for_status()
        resp_data = resp.json()
        status = resp_data["status"]
        assert status in ["initializing", "stopped"]
        if status == "stopped":
            break
        else:
            await sleep(0.1)

    resp = client.post("/manager/v1/node", json={"action": "start"})
    resp.raise_for_status()
    assert resp.json()["success"]

    resp = client.get("/manager/v1/node")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["status"] == "running"

    resp = client.post("/manager/v1/node", json={"action": "pause"})
    resp.raise_for_status()
    assert resp.json()["success"]

    resp = client.get("/manager/v1/node")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["status"] == "paused"

    resp = client.post("/manager/v1/node", json={"action": "resume"})
    resp.raise_for_status()
    assert resp.json()["success"]

    resp = client.get("/manager/v1/node")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["status"] == "running"

    resp = client.post("/manager/v1/node", json={"action": "stop"})
    resp.raise_for_status()
    assert resp.json()["success"]

    resp = client.get("/manager/v1/node")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["status"] == "stopped"
