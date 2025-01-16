import logging

from anyio import sleep
from pydantic import BaseModel

from crynux_server.contracts import wait_contracts

_logger = logging.getLogger(__name__)


class AccountInfo(BaseModel):
    address: str
    balance: int


_account_info = AccountInfo(address="", balance=0)


async def update_account_info(interval: int):
    contracts = await wait_contracts()

    _account_info.address = contracts.account

    while True:
        try:
            _account_info.balance = await contracts.get_balance(contracts.account)
        except Exception as e:
            _logger.error("get balance error")
            _logger.exception(e)
        await sleep(interval)


def get_account_info():
    return _account_info