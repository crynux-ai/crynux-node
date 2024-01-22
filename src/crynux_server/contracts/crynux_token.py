from typing import TYPE_CHECKING, Optional

from eth_typing import ChecksumAddress
from web3 import AsyncWeb3

from .utils import ContractWrapperBase, TxWaiter

if TYPE_CHECKING:
    from crynux_server.config import TxOption

__all__ = ["TokenContract"]


class TokenContract(ContractWrapperBase):
    def __init__(
        self, w3: AsyncWeb3, contract_address: Optional[ChecksumAddress] = None
    ):
        super().__init__(w3, "CrynuxToken", contract_address)

    async def balance_of(self, account: str) -> int:
        return await self._function_call("balanceOf", account=account)

    async def allowance(self, account: str) -> int:
        return await self._function_call(
            "allowance", owner=self.w3.eth.default_account, spender=account
        )

    async def transfer(
        self,
        to: str,
        amount: int,
        *,
        option: "Optional[TxOption]" = None,
    ) -> TxWaiter:
        return await self._transaction_call(
            "transfer", option=option, to=to, amount=amount
        )

    async def approve(
        self,
        spender: str,
        amount: int,
        *,
        option: "Optional[TxOption]" = None,
    ) -> TxWaiter:
        return await self._transaction_call(
            "approve", option=option, spender=spender, amount=amount
        )
