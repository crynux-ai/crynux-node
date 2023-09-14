import json
import secrets

import pytest
from eth_account import Account
from fastapi.testclient import TestClient
from httpx import HTTPStatusError

from h_server.config import wait_privkey


async def test_get_account_empty(client: TestClient):
    resp = client.get("/manager/v1/account")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["address"] == ""
    assert resp_data["eth_balance"] == 0
    assert resp_data["cnx_balance"] == 0


async def test_set_account(running_client: TestClient, privkeys):
    # test keystore file
    privkey = privkeys[1]
    password = "password"
    keystore = Account.encrypt(privkey, password)
    keystore_str = json.dumps(keystore)
    body = {"type": "keystore", "keystore": keystore_str, "passphrase": password}
    resp = running_client.post("/manager/v1/account", json=body)
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["success"]
    assert (await wait_privkey()) == privkey
    # test wrong keystore file
    body = {"type": "keystore", "keystore": keystore_str, "passphrase": "possward"}
    with pytest.raises(HTTPStatusError) as e:
        resp = running_client.post("/manager/v1/account", json=body)
        resp.raise_for_status()

    assert resp.status_code == 400
    # test private key
    privkey = privkeys[0]
    body = {
        "type": "private_key",
        "private_key": privkey,
    }

    resp = running_client.post("/manager/v1/account", json=body)
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["success"]

    assert (await wait_privkey()) == privkey


async def test_get_account(running_client: TestClient, accounts):
    resp = running_client.get("/manager/v1/account")
    resp.raise_for_status()
    resp_data = resp.json()
    assert resp_data["address"] == accounts[0]
    assert resp_data["eth_balance"] > 0
    assert resp_data["cnx_balance"] > 0
