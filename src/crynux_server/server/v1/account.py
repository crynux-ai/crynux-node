from fastapi import APIRouter, Body, HTTPException
from typing import Literal, Dict

from anyio import get_cancelled_exc_class, create_task_group
from eth_account import Account
from typing_extensions import Annotated
from pydantic import BaseModel, Field, SecretStr, Json

from anyio import to_thread
from crynux_server.config import set_privkey

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
        res = AccountInfo(address=contracts.account, eth_balance=0, cnx_balance=0)

        async def get_eth_balance():
            res.eth_balance = await contracts.get_balance(contracts.account)

        async def get_cnx_balance():
            res.cnx_balance = await contracts.token_contract.balance_of(
                contracts.account
            )

        async with create_task_group() as tg:
            tg.start_soon(get_eth_balance)
            tg.start_soon(get_cnx_balance)

        return res
    else:
        return AccountInfo(
            address="",
            eth_balance=0,
            cnx_balance=0,
        )


PrivkeyType = Literal["private_key", "keystore"]


class PrivkeyInput(BaseModel):
    type: PrivkeyType
    private_key: str = Field("", pattern=r"^0x[0-9a-fA-F]{64}$")
    keystore: Json[Dict] = dict()
    passphrase: SecretStr = SecretStr("")


@router.post("", response_model=CommonResponse)
async def set_account(input: Annotated[PrivkeyInput, Body()]):
    if input.type == "private_key":
        await set_privkey(input.private_key)
    if input.type == "keystore":
        try:
            privkey = await to_thread.run_sync(
                Account.decrypt, input.keystore, input.passphrase.get_secret_value()
            )
        except get_cancelled_exc_class():
            raise
        except Exception as e:
            raise HTTPException(400, str(e))
        await set_privkey(privkey.hex())

    return CommonResponse()
