from typing import TYPE_CHECKING, Optional

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3

from .utils import ContractWrapper, TxWaiter
from .utils import W3Pool

if TYPE_CHECKING:
    from crynux_server.config import TxOption

__all__ = ["TokenContract"]


class TokenContract(ContractWrapper):
    def __init__(
        self, w3_pool: W3Pool, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3_pool, "CrynuxToken", contract_address)

    async def balance_of(self, account: str , *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call("balanceOf", account=account, w3=w3)

    async def allowance(self, account: str, *, w3: Optional[AsyncWeb3] = None) -> int:
        return await self._function_call(
            "allowance", owner=self.w3_pool.account, spender=account, w3=w3
        )

    async def transfer(
        self,
        to: str,
        amount: int,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None
    ) -> TxWaiter:
        return await self._transaction_call(
            "transfer", option=option, to=to, amount=amount, w3=w3
        )

    async def approve(
        self,
        spender: str,
        amount: int,
        *,
        option: "Optional[TxOption]" = None,
        w3: Optional[AsyncWeb3] = None,
    ) -> TxWaiter:
        return await self._transaction_call(
            "approve", option=option, spender=spender, amount=amount, w3=w3
        )
