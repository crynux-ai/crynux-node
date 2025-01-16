import logging
from typing import Dict, Literal

from anyio import get_cancelled_exc_class, to_thread
from eth_account import Account
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field, Json, SecretStr
from typing_extensions import Annotated

from crynux_server.config import set_privkey

from .utils import CommonResponse
from ..depends import AccountInfoDep
from ..account import AccountInfo


router = APIRouter(prefix="/account")


@router.get("", response_model=AccountInfo)
async def get_account_info(*, account_info: AccountInfoDep):
    return account_info


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
        privkey = input.private_key
    else:
        try:
            privkey = (
                await to_thread.run_sync(
                    Account.decrypt, input.keystore, input.passphrase.get_secret_value()
                )
            ).hex()
        except get_cancelled_exc_class():
            raise
        except Exception as e:
            raise HTTPException(400, str(e))
        await set_privkey(privkey)

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
