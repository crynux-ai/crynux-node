import json
from contextlib import asynccontextmanager
from typing import (TYPE_CHECKING, Any, Callable, Dict, List, Optional,
                    TypeVar, cast)

import importlib_resources as impresources
from eth_abi.abi import decode
from eth_typing import ChecksumAddress
from hexbytes import HexBytes
from typing_extensions import ParamSpec
from web3 import AsyncWeb3
from web3.contract.async_contract import (AsyncContract, AsyncContractEvent,
                                          AsyncContractFunction)
from web3.exceptions import ContractLogicError
from web3.logs import WARN
from web3.types import EventData, TxParams, TxReceipt

from crynux_server.config import get_default_tx_option

from .exceptions import TxRevertedError
from .w3_pool import W3Pool

if TYPE_CHECKING:
    from crynux_server.config import TxOption


def read_abi(name: str):
    file = impresources.files("crynux_server.contracts.abi") / f"{name}.json"
    with file.open("r", encoding="utf-8") as f:  # type: ignore
        content = json.load(f)

    return content["abi"], content["bytecode"]


Contract_Func = Callable[[], AsyncContract]

T = TypeVar("T")
P = ParamSpec("P")


@asynccontextmanager
async def catch_tx_revert_error(method: str):
    try:
        yield
    except ContractLogicError as e:
        reason = ""
        if e.message is not None:
            reason = e.message
        elif e.data is not None and isinstance(e.data, str):
            if e.data.startswith("08c379a0"):
                reason_hex = e.data[8:]
                reason: str = decode(["string"], bytes.fromhex(reason_hex))[0]

        raise TxRevertedError(method=method, reason=reason) from e


class TxWaiter(object):
    def __init__(
        self,
        w3_pool: W3Pool,
        method: str,
        tx_hash: HexBytes,
        timeout: float = 120,
        interval: float = 0.1,
    ):
        self.w3_pool = w3_pool
        self.method = method
        self.tx_hash = tx_hash
        self.timeout = timeout
        self.interval = interval

    async def wait(self, w3: Optional[AsyncWeb3] = None) -> TxReceipt:
        async def _wait_receipt(w3: AsyncWeb3):
            receipt = await w3.eth.wait_for_transaction_receipt(
                self.tx_hash, self.timeout, self.interval
            )
            if not receipt["status"]:
                async with catch_tx_revert_error(self.method):
                    tx = await w3.eth.get_transaction(self.tx_hash)
                    tx_params: TxParams = {
                        "to": tx["to"],
                        "from": tx["from"],
                        "value": tx["value"],
                        "data": tx["data"],
                        "chainId": tx["chainId"],
                        "gas": tx["gas"],
                        "gasPrice": tx["gasPrice"],
                    }
                    blocknum = tx["blockNumber"] - 1
                    await w3.eth.call(
                        tx_params,
                        blocknum,
                    )
                    raise TxRevertedError(
                        method=self.method,
                        reason=f"Unknown error: {tx_params} on block {blocknum}",
                    )
            return receipt

        if w3 is None:
            async with await self.w3_pool.get() as w3:
                return await _wait_receipt(w3)
        else:
            return await _wait_receipt(w3)


class ContractWrapper(object):
    def __init__(
        self,
        w3_pool: W3Pool,
        contract_name: str,
        contract_address: Optional[ChecksumAddress] = None,
    ):
        self.w3_pool = w3_pool

        abi, bytecode = read_abi(contract_name)
        self.abi = abi
        self.bytecode = bytecode
        self._address = contract_address

    async def deploy(self, *args, **kwargs):
        assert self._address is None, "Contract has been deployed"

        w3: Optional[AsyncWeb3] = kwargs.pop("w3", None)

        async def _deploy(w3: AsyncWeb3):
            option = kwargs.pop("option", None)

            opt: TxParams = {}
            if option is not None:
                opt.update(**option)
            else:
                opt.update(**get_default_tx_option())

            _contract_builder = w3.eth.contract(abi=self.abi, bytecode=self.bytecode)
            async with self.w3_pool.with_nonce_lock():
                if "nonce" not in opt:
                    nonce = await w3.eth.get_transaction_count(
                        account=self.w3_pool.account, block_identifier="pending"
                    )
                    opt["nonce"] = nonce
                if "from" not in opt:
                    opt["from"] = self.w3_pool.account

                async with catch_tx_revert_error("deploy"):
                    tx_hash = await _contract_builder.constructor(
                        *args, **kwargs
                    ).transact(  # type: ignore
                        opt
                    )
            waiter = TxWaiter(self.w3_pool, "deploy", tx_hash=tx_hash)
            receipt = await waiter.wait(w3=w3)
            address = receipt["contractAddress"]
            assert address is not None, "Deployed contract address is None"
            self._address = address
            return waiter

        if w3 is None:
            async with await self.w3_pool.get() as w3:
                return await _deploy(w3)
        else:
            return await _deploy(w3)

    @property
    def address(self) -> ChecksumAddress:
        assert self._address is not None, "Contract has not been deployed"
        return self._address

    async def _transaction_call(
        self,
        method: str,
        timeout: float = 120,
        interval: float = 0.1,
        option: Optional["TxOption"] = None,
        w3: Optional[AsyncWeb3] = None,
        **kwargs,
    ):
        assert self._address is not None, "Contract has not been deployed"

        async def _send_tx(w3: AsyncWeb3):
            opt: TxParams = {}
            if option is not None:
                opt.update(**option)
            else:
                opt.update(**get_default_tx_option())

            contract = w3.eth.contract(address=self._address, abi=self.abi)
            async with self.w3_pool.with_nonce_lock():
                opt["from"] = self.w3_pool.account
                nonce = await w3.eth.get_transaction_count(
                    account=self.w3_pool.account, block_identifier="pending"
                )
                opt["nonce"] = nonce
                tx_func: AsyncContractFunction = getattr(contract.functions, method)
                async with catch_tx_revert_error(method):
                    tx_hash: HexBytes = await tx_func(**kwargs).transact(opt)
            return tx_hash

        if w3 is None:
            async with await self.w3_pool.get() as w3:
                tx_hash = await _send_tx(w3)
        else:
            tx_hash = await _send_tx(w3)

        return TxWaiter(
            w3_pool=self.w3_pool,
            method=method,
            tx_hash=tx_hash,
            timeout=timeout,
            interval=interval,
        )

    async def _function_call(self, method: str, *args, **kwargs):
        assert self._address is not None, "Contract has not been deployed"

        async def _call(w3: AsyncWeb3):
            opt: TxParams = {}
            opt["from"] = self.w3_pool.account
            contract = w3.eth.contract(address=self._address, abi=self.abi)

            tx_func: AsyncContractFunction = getattr(contract.functions, method)
            return await tx_func(*args, **kwargs).call(opt)

        w3: Optional[AsyncWeb3] = kwargs.pop("w3", None)

        if w3 is None:
            async with await self.w3_pool.get() as w3:
                return await _call(w3)
        else:
            return await _call(w3)

    async def get_events(
        self,
        event_name: str,
        filter_args: Optional[Dict[str, Any]] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        w3: Optional[AsyncWeb3] = None,
    ) -> List[EventData]:
        assert self._address is not None, "Contract has not been deployed"

        async def _get_events(w3: AsyncWeb3):
            contract = w3.eth.contract(address=self._address, abi=self.abi)
            event = contract.events[event_name]
            event = cast(AsyncContractEvent, event)
            events = await event.get_logs(
                argument_filters=filter_args, fromBlock=from_block, toBlock=to_block
            )
            return list(events)

        if w3 is None:
            async with await self.w3_pool.get() as w3:
                return await _get_events(w3)
        else:
            return await _get_events(w3)

    async def event_process_receipt(
        self,
        event_name: str,
        recepit: TxReceipt,
        errors=WARN,
        w3: Optional[AsyncWeb3] = None,
    ) -> List[EventData]:
        assert self._address is not None, "Contract has not been deployed"

        async def _process_receipt(w3: AsyncWeb3):
            contract = w3.eth.contract(address=self._address, abi=self.abi)
            event = contract.events[event_name]
            event = cast(AsyncContractEvent, event)
            return event.process_receipt(recepit, errors=errors)

        if w3 is None:
            async with await self.w3_pool.get() as w3:
                return await _process_receipt(w3)
        else:
            return await _process_receipt(w3)
