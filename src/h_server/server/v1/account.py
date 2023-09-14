from fastapi import APIRouter, Body, HTTPException
from typing import Literal

from eth_account import Account
from typing_extensions import Annotated
from pydantic import BaseModel, Field, SecretStr

from anyio import to_thread
from h_server.config import set_privkey

from .utils import CommonResponse
from ..depends import ContractsDep

router = APIRouter(prefix="/account")


class AccountInfo(BaseModel):
    address: str
    eth_balance: int
    cnx_balance: int


@router.get("", response_model=AccountInfo)
async def get_account_info(*, contracts: ContractsDep):
    if contracts is not None:
        eth_balance = await contracts.get_balance(contracts.account)
        cnx_balance = await contracts.token_contract.balance_of(contracts.account)
        return AccountInfo(
            address=contracts.account, eth_balance=eth_balance, cnx_balance=cnx_balance
        )
    else:
        return AccountInfo(
            address="", eth_balance=0, cnx_balance=0,
        )

PrivkeyType = Literal["private_key", "keystore"]


class PrivkeyInput(BaseModel):
    type: PrivkeyType
    private_key: str = Field("", pattern=r"^0x[0-9a-fA-F]+$")
    keystore: str = ""
    passphrase: SecretStr = SecretStr("")


@router.post("", response_model=CommonResponse)
async def set_account(input: Annotated[PrivkeyInput, Body()]):
    if input.type == "private_key":
        assert len(input.private_key) > 0, HTTPException(400, "Private key is empty")
        await set_privkey(input.private_key)
    if input.type == "keystore":
        assert len(input.keystore) > 0 and len(input.passphrase) > 0

        try:
            privkey = await to_thread.run_sync(
                Account.decrypt, input.keystore, input.passphrase.get_secret_value()
            )
        except (TypeError, ValueError) as e:
            raise HTTPException(400, str(e))
        await set_privkey(privkey.hex())

    return CommonResponse()
