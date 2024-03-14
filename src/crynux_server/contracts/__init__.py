import logging
from typing import cast, Optional

from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from web3 import AsyncWeb3
from web3.types import TxParams
from web3.middleware.signing import async_construct_sign_and_send_raw_middleware
from web3.providers.async_base import AsyncBaseProvider

from . import crynux_token, node, task, qos, task_queue, network_stats
from .exceptions import TxRevertedError
from .utils import TxWaiter

from crynux_server.config import get_default_tx_option, TxOption


__all__ = ["TxRevertedError", "Contracts", "TxWaiter", "get_contracts", "set_contracts"]

_logger = logging.getLogger(__name__)


class Contracts(object):
    node_contract: node.NodeContract
    task_contract: task.TaskContract
    token_contract: crynux_token.TokenContract
    qos_contract: qos.QOSContract
    task_queue_contract: task_queue.TaskQueueContract
    netstats_contract: network_stats.NetworkStatsContract

    def __init__(
        self,
        provider: Optional[AsyncBaseProvider] = None,
        provider_path: Optional[str] = None,
        privkey: str = "",
        default_account_index: Optional[int] = None,
        timeout: int = 30,
    ):
        if provider is None:
            if provider_path is None:
                raise ValueError("provider and provider_path cannot be all None.")
            if provider_path.startswith("http"):
                from web3 import AsyncHTTPProvider

                provider = AsyncHTTPProvider(
                    provider_path, request_kwargs={"timeout": timeout}
                )
            elif provider_path.startswith("ws"):
                from web3 import WebsocketProviderV2

                provider = WebsocketProviderV2(provider_path, call_timeout=timeout)
            else:
                raise ValueError(f"unsupported provider {provider_path}")

        self.provider = provider
        self._w3 = AsyncWeb3(self.provider)
        self._privkey = privkey
        self._default_account_index = default_account_index

        self._initialized = False

    async def init(
        self,
        token_contract_address: Optional[str] = None,
        node_contract_address: Optional[str] = None,
        task_contract_address: Optional[str] = None,
        qos_contract_address: Optional[str] = None,
        task_queue_contract_address: Optional[str] = None,
        netstats_contract_address: Optional[str] = None,
        *,
        option: "Optional[TxOption]" = None,
    ):
        if self._privkey != "":
            account: LocalAccount = self._w3.eth.account.from_key(self._privkey)
            middleware = await async_construct_sign_and_send_raw_middleware(account)
            self._w3.middleware_onion.add(middleware)
            self._w3.eth.default_account = account.address
        elif self._default_account_index is not None:
            self._w3.eth.default_account = (await self._w3.eth.accounts)[
                self._default_account_index
            ]
        _logger.info(f"Wallet address is {self._w3.eth.default_account}")

        if option is None:
            option = get_default_tx_option()

        if token_contract_address is not None:
            self.token_contract = crynux_token.TokenContract(
                self.w3, self.w3.to_checksum_address(token_contract_address)
            )
        else:
            self.token_contract = crynux_token.TokenContract(self.w3)
            await self.token_contract.deploy(option=option)
            token_contract_address = self.token_contract.address

        if qos_contract_address is not None:
            self.qos_contract = qos.QOSContract(
                self.w3, self.w3.to_checksum_address(qos_contract_address)
            )
        elif task_contract_address is None:
            # task contract has not been deployed, need deploy qos contract
            self.qos_contract = qos.QOSContract(self.w3)
            await self.qos_contract.deploy(option=option)
            qos_contract_address = self.qos_contract.address

        if task_queue_contract_address is not None:
            self.task_queue_contract = task_queue.TaskQueueContract(
                self.w3, self.w3.to_checksum_address(task_queue_contract_address)
            )
        elif task_contract_address is None:
            # task contract has not been deployed, need deploy qos contract
            self.task_queue_contract = task_queue.TaskQueueContract(self.w3)
            await self.task_queue_contract.deploy(option=option)
            task_queue_contract_address = self.task_queue_contract.address

        if netstats_contract_address is not None:
            self.netstats_contract = network_stats.NetworkStatsContract(
                self.w3, self.w3.to_checksum_address(netstats_contract_address)
            )
        elif task_contract_address is None:
            # task contract has not been deployed, need deploy qos contract
            self.netstats_contract = network_stats.NetworkStatsContract(self.w3)
            await self.netstats_contract.deploy(option=option)
            netstats_contract_address = self.netstats_contract.address

        if node_contract_address is not None:
            self.node_contract = node.NodeContract(
                self.w3, self.w3.to_checksum_address(node_contract_address)
            )
        else:
            assert qos_contract_address is not None, "QOS contract address is None"
            assert netstats_contract_address is not None, "NetworkStats contract address is None"
            self.node_contract = node.NodeContract(self.w3)
            await self.node_contract.deploy(
                token_contract_address,
                qos_contract_address,
                netstats_contract_address,
                option=option,
            )
            node_contract_address = self.node_contract.address
            await self.qos_contract.update_node_contract_address(
                node_contract_address, option=option
            )
            await self.netstats_contract.update_node_contract_address(
                node_contract_address, option=option
            )

        if task_contract_address is not None:
            self.task_contract = task.TaskContract(
                self.w3, self.w3.to_checksum_address(task_contract_address)
            )
        else:
            assert qos_contract_address is not None, "QOS contract address is None"
            assert task_queue_contract_address is not None, "Task queue contract address is None"
            assert netstats_contract_address is not None, "NetworkStats contract address is None"

            self.task_contract = task.TaskContract(self.w3)
            await self.task_contract.deploy(
                node_contract_address,
                token_contract_address,
                qos_contract_address,
                task_queue_contract_address,
                netstats_contract_address,
                option=option,
            )
            task_contract_address = self.task_contract.address

            await self.node_contract.update_task_contract_address(
                task_contract_address, option=option
            )
            await self.qos_contract.update_task_contract_address(
                task_contract_address, option=option
            )
            await self.task_queue_contract.update_task_contract_address(
                task_contract_address, option=option
            )
            await self.netstats_contract.update_task_contract_address(
                task_contract_address, option=option
            )

        self._initialized = True

    @property
    def w3(self):
        return self._w3

    @property
    def account(self) -> ChecksumAddress:
        res = self._w3.eth.default_account
        assert res, "Contracts has not been initialized!"
        return res

    @property
    def initialized(self) -> bool:
        return self._initialized

    async def get_current_block_number(self) -> int:
        return await self._w3.eth.get_block_number()

    async def get_balance(self, account: ChecksumAddress) -> int:
        return await self.w3.eth.get_balance(account)

    async def transfer(
        self, to: str, amount: int, *, option: "Optional[TxOption]" = None
    ):
        if option is None:
            option = get_default_tx_option()
        opt = cast(TxParams, option.copy())
        opt["to"] = self.w3.to_checksum_address(to)
        opt["from"] = self.account
        opt["value"] = self.w3.to_wei(amount, "Wei")

        tx_hash = await self.w3.eth.send_transaction(opt)
        receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt


_default_contracts: Optional[Contracts] = None


def get_contracts() -> Contracts:
    assert _default_contracts is not None, "Contracts has not been set."

    return _default_contracts


def set_contracts(contracts: Contracts):
    global _default_contracts

    _default_contracts = contracts
