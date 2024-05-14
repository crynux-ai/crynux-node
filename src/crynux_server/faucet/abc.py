from abc import ABC, abstractmethod

class Faucet(ABC):
    @abstractmethod
    async def request_token(self, address: str) -> bool:
        ...

    @abstractmethod
    async def close(self):
        ...
