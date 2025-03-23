import logging

from anyio import sleep
from pydantic import BaseModel

from crynux_server.config import wait_privkey
from crynux_server.relay import get_relay
from crynux_server.utils import get_address_from_privkey

_logger = logging.getLogger(__name__)


class AccountInfo(BaseModel):
    address: str
    balance: int


_account_info = AccountInfo(address="", balance=0)


async def update_account_info(interval: int):
    privkey = await wait_privkey()
    _account_info.address = get_address_from_privkey(privkey)

    while True:
        try:
            relay = get_relay()

            try:
                _account_info.balance = await relay.get_balance()
            except Exception as e:
                _logger.error("get balance error")
                _logger.exception(e)
        except AssertionError:
            pass
        await sleep(interval)


def get_account_info():
    return _account_info