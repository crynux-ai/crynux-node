import logging
from typing import Any, Awaitable, Callable, Dict, Optional, cast

from anyio import CancelScope, Event, create_task_group, fail_after, sleep
from anyio.abc import TaskGroup
from web3 import AsyncWeb3
from web3.contract.async_contract import AsyncContract, AsyncContractEvent
from web3.types import EventData, TxReceipt
from web3.logs import DISCARD

from h_server.contracts import Contracts

from .block_cache import BlockNumberCache

EventCallback = Callable[[EventData], Awaitable[None]]

_logger = logging.getLogger(__name__)


def wrap_callback(callback: EventCallback) -> EventCallback:
    async def inner(event: EventData):
        try:
            return await callback(event)
        except Exception as e:
            _logger.exception(e)
            _logger.error(f"Watcher callback for event {event} failed.")

    return inner

class EventFilter(object):
    def __init__(
        self,
        event: AsyncContractEvent,
        callback: EventCallback,
        filter_args: Optional[Dict[str, Any]] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
    ):
        self.event = event
        self.callback = callback
        self.filter_args = filter_args
        self.from_block = from_block
        self.to_block = to_block

    def process_tx(self, tx: TxReceipt, tg: TaskGroup):
        block_number = tx["blockNumber"]
        if self.from_block is not None and self.from_block >= block_number:
            return
        if self.to_block is not None and self.to_block < block_number:
            return
        if tx["to"] != self.event.address:
            return
        for event in self.event.process_receipt(tx, errors=DISCARD):
            if _filter_event(event, self.filter_args):
                _logger.debug(f"Watch event: {event}")
                tg.start_soon(wrap_callback(self.callback), event)


def _filter_event(event: EventData, filter_args: Optional[Dict[str, Any]]) -> bool:
    if filter_args is None:
        return True
    for key, value in filter_args.items():
        real = event["args"][key]
        if isinstance(value, list):
            if real not in value:
                return False
        elif real != value:
            return False

    return True


class EventWatcher(object):
    def __init__(self, w3: AsyncWeb3) -> None:
        self.w3 = w3

        self._event_filters: Dict[int, EventFilter] = {}
        self._next_filter_id: int = 0

        self._contracts: Dict[str, AsyncContract] = {}

        self._cache: Optional[BlockNumberCache] = None

        self._cancel_scope: Optional[CancelScope] = None
        self._stop_event: Optional[Event] = None

    @classmethod
    def from_contracts(cls, contracts: Contracts) -> "EventWatcher":
        assert contracts.initialized, "Contracts has not been initialized!"

        res = cls(contracts.w3)
        res.register_contract("token", contracts.token_contract.contract)
        res.register_contract("node", contracts.node_contract.contract)
        res.register_contract("task", contracts.task_contract.contract)
        return res

    def register_contract(self, name: str, contract: AsyncContract):
        self._contracts[name] = contract

    def set_blocknumber_cache(self, cache: BlockNumberCache):
        self._cache = cache

    def remove_blocknumber_cache(self):
        self._cache = None

    def watch_event(
        self,
        contract_name: str,
        event_name: str,
        callback: EventCallback,
        filter_args: Optional[Dict[str, Any]] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
    ) -> int:
        contract = self._contracts[contract_name]
        event = contract.events[event_name]()
        event = cast(AsyncContractEvent, event)

        event_filter = EventFilter(
            event=event,
            callback=callback,
            filter_args=filter_args,
            from_block=from_block,
            to_block=to_block,
        )
        filter_id = self._next_filter_id
        self._event_filters[filter_id] = event_filter
        self._next_filter_id += 1
        _logger.debug(f"Watch event {contract_name}.{event_name}, {filter_args}")
        return filter_id

    def unwatch_event(self, filter_id: int):
        if filter_id in self._event_filters:
            self._event_filters.pop(filter_id)

    async def start(
        self,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        interval: float = 1,
    ):
        """
        watch events from block

        from_block: a block number or None, None means start from the latest block
        to_block: a block number or None, None means watch infinitely
        interval: sleep time, sleep when there is no new block
        """
        assert (
            self._cancel_scope is None
        ), "The watcher has already started. You should stop the watcher before restart it."
        assert (
            self._stop_event is None
        ), "The watcher has already started. You should stop the watcher before restart it."

        self._stop_event = Event()

        if from_block is None:
            if self._cache is not None:
                start = await self._cache.get()
                if start == 0:
                    start = await self.w3.eth.get_block_number()
            else:
                start = await self.w3.eth.get_block_number()
        else:
            if self._cache is not None:
                await self._cache.set(from_block)
            start = from_block

        def _should_stop(stop_event: Event, start: int):
            if stop_event.is_set():
                return True
            if to_block is None:
                return False
            return start > to_block

        try:
            self._cancel_scope = CancelScope()
            with self._cancel_scope:
                while not _should_stop(self._stop_event, start):
                    if start <= (await self.w3.eth.get_block_number()):
                        block = await self.w3.eth.get_block(start)
                        if "transactions" in block and len(self._event_filters) > 0:
                            async with create_task_group() as tg:
                                for tx_hash in block["transactions"]:
                                    assert isinstance(tx_hash, bytes)
                                    tx = await self.w3.eth.get_transaction_receipt(
                                        tx_hash
                                    )
                                    for event_filter in self._event_filters.values():
                                        event_filter.process_tx(tx, tg=tg)

                        start += 1

                        with fail_after(delay=5, shield=True):
                            if self._cache is not None:
                                await self._cache.set(start + 1)
                    else:
                        await sleep(interval)
        finally:
            self._cancel_scope = None
            self._stop_event = None

    def stop(self):
        assert self._stop_event is not None, "The watcher has not been started."
        assert self._cancel_scope is not None, "The watcher has not been started."
        self._stop_event.set()
        if not self._cancel_scope.cancel_called:
            self._cancel_scope.cancel()
