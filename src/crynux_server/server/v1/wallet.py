from eth_account import Account
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/wallet")


class WalletResponse(BaseModel):
    address: str
    privkey: str


@router.get("", response_model=WalletResponse)
async def create_wallet():
    acct = Account.create()
    return WalletResponse(address=acct.address, privkey=acct.key.hex())
