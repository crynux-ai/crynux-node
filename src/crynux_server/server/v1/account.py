import logging
from typing import Dict, Literal

from anyio import create_task_group, get_cancelled_exc_class, to_thread
from eth_account import Account
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field, Json, SecretStr
from typing_extensions import Annotated

from crynux_server.config import get_privkey, set_privkey
from crynux_server.contracts import wait_contracts

from ..depends import FaucetDep
from .utils import CommonResponse

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account")


class AccountInfo(BaseModel):
    address: str
    balance: int


@router.get("", response_model=AccountInfo)
async def get_account_info():
    privkey = get_privkey()
    if privkey == "":
        return AccountInfo(
            address="",
            balance=0,
        )
    else:
        contracts = await wait_contracts()
        res = AccountInfo(address=contracts.account, balance=0)

        try:
            res.balance = await contracts.get_balance(contracts.account)
        except Exception as e:
            _logger.error(e)
            raise HTTPException(status_code=500, detail=f"ContractError: {str(e)}")

        return res


PrivkeyType = Literal["private_key", "keystore"]


class PrivkeyInput(BaseModel):
    type: PrivkeyType
    private_key: str = Field("", pattern=r"^0x[0-9a-fA-F]{64}$")
    keystore: Json[Dict] = dict()
    passphrase: SecretStr = SecretStr("")


@router.put("", response_model=CommonResponse)
async def set_account(input: Annotated[PrivkeyInput, Body()], *, faucet: FaucetDep):
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

    acct = Account.from_key(privkey)
    address = acct.address
    await faucet.request_token(address)

    return CommonResponse()


class AccountWithKey(BaseModel):
    address: str
    key: str


@router.post("", response_model=AccountWithKey)
async def create_account(*, faucet: FaucetDep):
    acct = Account.create()
    address: str = acct.address
    privkey: str = acct.key.hex()
    await set_privkey(privkey=privkey)
    await faucet.request_token(address)

    return AccountWithKey(address=address, key=privkey)
