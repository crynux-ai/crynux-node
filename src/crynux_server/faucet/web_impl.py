import httpx

from .abc import Faucet


class WebFaucet(Faucet):
    def __init__(self, url: str) -> None:
        self.client = httpx.AsyncClient(base_url=url, timeout=30)

    async def request_token(self, address: str):
        input = {"address": address}

        resp = await self.client.post("/v1/faucet", json=input)
        resp.raise_for_status()
        content = resp.json()
        success: bool = content["success"]
        return success

    async def close(self):
        await self.client.aclose()
