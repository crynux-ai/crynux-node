from .abc import Faucet

class MockFaucet(Faucet):
    async def request_token(self, address: str) -> bool:
        return True

    async def close(self):
        pass
