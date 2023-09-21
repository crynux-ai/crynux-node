import json
from typing import TYPE_CHECKING, Callable, Optional, TypeVar, cast

import importlib_resources as impresources
from anyio import Lock, get_cancelled_exc_class
from eth_typing import ChecksumAddress
from hexbytes import HexBytes
from typing_extensions import ParamSpec
from web3 import AsyncWeb3
from web3.contract import AsyncContract
from web3.contract.async_contract import AsyncContractFunction
from web3.types import TxParams

from h_server.config import get_default_tx_option

from .exceptions import TxRevertedError

if TYPE_CHECKING:
    from h_server.config import TxOption


def read_abi(name: str):
    file = impresources.files("h_server.contracts.abi") / f"{name}.json"
    with file.open("r", encoding="utf-8") as f:  # type: ignore
        content = json.load(f)

    return content["abi"], content["bytecode"]


Contract_Func = Callable[[], AsyncContract]

T = TypeVar("T")
P = ParamSpec("P")

class TxWaiter(object):
    def __init__(self, w3: AsyncWeb3, method: str, tx_hash: HexBytes, timeout: float = 120,interval: float = 0.1):
        self.w3 = w3
        self.method = method
        self.tx_hash = tx_hash
        self.timeout = timeout
        self.interval = interval

    async def wait(self):
        receipt = await self.w3.eth.wait_for_transaction_receipt(
            self.tx_hash, self.timeout, self.interval
        )
        if not receipt["status"]:
            try:
                tx = await self.w3.eth.get_transaction(self.tx_hash)
                await self.w3.eth.call(
                    {
                        "to": tx["to"],
                        "from": tx["from"],
                        "value": tx["value"],
                        "data": tx["input"],
                        "chainId": tx["chainId"],
                        "gas": tx["gas"],
                        "gasPrice": tx["gasPrice"],
                    },
                    tx["blockNumber"] - 1,
                )
                raise TxRevertedError(method=self.method, reason="Unknown")
            except (TxRevertedError, get_cancelled_exc_class()):
                raise
            except Exception as e:
                reason = str(e)
                raise TxRevertedError(method=self.method, reason=reason)
        return receipt
        

class ContractWrapperBase(object):
    def __init__(
        self,
        w3: AsyncWeb3,
        contract_name: str,
        contract_address: Optional[ChecksumAddress] = None,
    ):
        self.w3 = w3

        abi, bytecode = read_abi(contract_name)
        self._address = contract_address
        if contract_address is not None:
            self._contract = w3.eth.contract(address=contract_address, abi=abi)
            self._contract_builder = None
        else:
            self._contract = None
            self._contract_builder = w3.eth.contract(abi=abi, bytecode=bytecode)

        self._nonce_lock = Lock()

    async def deploy(self, *args, **kwargs):
        assert (
            self._contract is None and self._contract_builder is not None
        ), "Contract has been deployed"
        option = kwargs.pop("option", None)
        if option is None:
            option = get_default_tx_option()

        option = cast(TxParams, option.copy())
        async with self._nonce_lock:
            assert self.w3.eth.default_account, "The default account is empty."
            if "nonce" not in option:
                nonce = await self.w3.eth.get_transaction_count(
                    account=self.w3.eth.default_account, block_identifier="pending"
                )
                option["nonce"] = nonce
            if "from" not in option:
                option["from"] = self.w3.eth.default_account

            tx_hash = await self._contract_builder.constructor(
                *args, **kwargs
            ).transact(  # type: ignore
                option
            )
        waiter = TxWaiter(self.w3, "deploy", tx_hash=tx_hash)
        receipt = await waiter.wait()
        address = receipt["contractAddress"]
        assert address is not None, "Deployed contract address is None"
        self._address = address
        self._contract = self.w3.eth.contract(
            address=address, abi=self._contract_builder.abi
        )
        self._contract_builder = None

    @property
    def address(self) -> ChecksumAddress:
        assert self._address is not None, "Contract has not been deployed"
        return self._address

    @property
    def contract(self) -> AsyncContract:
        assert self._contract is not None, "Contract has not been deployed"
        return self._contract

    async def _transaction_call(
        self,
        method: str,
        timeout: float = 120,
        interval: float = 0.1,
        option: Optional["TxOption"] = None,
        *args,
        **kwargs,
    ):
        if option is None:
            option = get_default_tx_option()

        opt = cast(TxParams, option.copy())
        async with self._nonce_lock:
            assert self.w3.eth.default_account, "The default account is empty."
            opt["from"] = self.w3.eth.default_account
            nonce = await self.w3.eth.get_transaction_count(
                account=self.w3.eth.default_account, block_identifier="pending"
            )
            opt["nonce"] = nonce
            tx_func: AsyncContractFunction = getattr(self.contract.functions, method)
            tx_hash: HexBytes = await tx_func(*args, **kwargs).transact(opt)

        return TxWaiter(w3=self.w3, method=method, tx_hash=tx_hash, timeout=timeout, interval=interval)

    async def _function_call(self, method: str, *args, **kwargs):
        opt: TxParams = {}
        assert self.w3.eth.default_account, "The default account is empty."
        opt["from"] = self.w3.eth.default_account

        tx_func: AsyncContractFunction = getattr(self.contract.functions, method)
        return await tx_func(*args, **kwargs).call(opt)
