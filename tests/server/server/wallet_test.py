from fastapi.testclient import TestClient

async def test_get_wallet(running_client: TestClient):
    addresses = []
    privkeys = []
    
    for _ in range(3):
        resp = running_client.get("/manager/v1/wallet")
        resp.raise_for_status()
        resp_data = resp.json()

        address = resp_data["address"]
        privkey = resp_data["privkey"]

        assert len(address) == 42
        assert len(privkey) == 66

        addresses.append(address)
        privkeys.append(privkey)

    assert all(addr != address[0] for addr in addresses[1:])
    assert all(key != privkeys[0] for key in privkeys[1:])

