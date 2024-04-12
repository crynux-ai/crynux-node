import logging
from typing import Dict, Literal

from anyio import create_task_group, get_cancelled_exc_class, to_thread
from eth_account import Account
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field, Json, SecretStr
from typing_extensions import Annotated

from crynux_server.config import set_privkey

from ..depends import ContractsDep
from .utils import CommonResponse

_logger = logging.getLogger(__name__)

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

        try:
            async with create_task_group() as tg:
                tg.start_soon(get_eth_balance)
                tg.start_soon(get_cnx_balance)
        except Exception as e:
            _logger.error(e)
            raise HTTPException(status_code=500, detail=f"ContractError: {str(e)}")

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


@router.put("", response_model=CommonResponse)
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


class AccountWithKey(BaseModel):
    address: str
    key: str


@router.post("", response_model=AccountWithKey)
async def create_account():
    acct = Account.create()
    address: str = acct.address
    privkey: str = acct.key.hex()
    await set_privkey(privkey=privkey)

    return AccountWithKey(address=address, key=privkey)
