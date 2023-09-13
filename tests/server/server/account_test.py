from fastapi.testclient import TestClient
from h_server.config import wait_privkey


async def test_set_account(client: TestClient):
    body = {
        "type": "private_key",
        "private_key": "0x420fcabfd5dbb55215490693062e6e530840c64de837d071f0d9da21aaac861e"
    }

    resp = client.post("/manager/v1/account", json=body)
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["success"]

    assert (await wait_privkey()) == body["private_key"]


async def test_get_account(client: TestClient, accounts):
    resp = client.get("/manager/v1/account")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["address"] == accounts[0]
    assert resp_data["eth_balance"] > 0
    assert resp_data["cnx_balance"] > 0
