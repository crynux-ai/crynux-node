import json

import pytest
from eth_account import Account
from fastapi.testclient import TestClient
from httpx import HTTPStatusError

from crynux_server.config import wait_privkey


async def test_get_account_empty(client: TestClient):
    resp = client.get("/manager/v1/account")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["address"] == ""
    assert resp_data["eth_balance"] == 0
    assert resp_data["cnx_balance"] == 0


async def test_create_account(running_client: TestClient):
    resp = running_client.post("/manager/v1/account")
    resp.raise_for_status()

    address1 = resp.json()["address"]
    privkey1 = resp.json()["key"]

    assert (await wait_privkey()) == privkey1

    resp = running_client.post("/manager/v1/account")
    resp.raise_for_status()

    address2 = resp.json()["address"]
    privkey2 = resp.json()["key"]

    assert (await wait_privkey()) == privkey2
    assert address1 != address2
    assert privkey1 != privkey2


async def test_set_account(running_client: TestClient, privkeys):
    body = {"type": "keystore", "keystore": "123", "passphrase": "possward"}
    with pytest.raises(HTTPStatusError) as e:
        resp = running_client.put("/manager/v1/account", json=body)
        assert resp.status_code == 422
        resp.raise_for_status()

    # test keystore file
    privkey = privkeys[1]
    password = "password"
    keystore = Account.encrypt(privkey, password)
    keystore_str = json.dumps(keystore)
    body = {"type": "keystore", "keystore": keystore_str, "passphrase": password}
    resp = running_client.put("/manager/v1/account", json=body)
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["success"]
    assert (await wait_privkey()) == privkey
    # test wrong keystore file
    body = {"type": "keystore", "keystore": keystore_str, "passphrase": "possward"}
    with pytest.raises(HTTPStatusError) as e:
        resp = running_client.put("/manager/v1/account", json=body)
        assert resp.status_code == 400
        resp.raise_for_status()

    # test private key
    privkey = privkeys[0]
    body = {
        "type": "private_key",
        "private_key": privkey,
    }

    resp = running_client.put("/manager/v1/account", json=body)
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["success"]

    assert (await wait_privkey()) == privkey


async def test_get_account(running_client: TestClient, accounts, privkeys):
    resp = running_client.get("/manager/v1/account")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["address"] == accounts[0]
    assert resp_data["eth_balance"] > 0
