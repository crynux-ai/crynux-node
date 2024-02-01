import logging
from typing import Any, Awaitable, Callable, Dict, Optional, cast

from anyio import CancelScope, Event, create_task_group, fail_after, sleep
from anyio.abc import TaskGroup
from tenacity import (AsyncRetrying, before_sleep_log, stop_after_attempt,
                      wait_fixed)
from web3 import AsyncWeb3
from web3.contract.async_contract import AsyncContract, AsyncContractEvent
from web3.types import EventData

from crynux_server.contracts import Contracts

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
        filter_id: int,
        event: AsyncContractEvent,
        callback: EventCallback,
        filter_args: Optional[Dict[str, Any]] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
    ):
        self.filter_id = filter_id
        self.event: AsyncContractEvent = event
        self.callback = callback
        self.filter_args = filter_args
        self.from_block = from_block
        self.to_block = to_block

    async def process_events(self, start: int, end: int, tg: TaskGroup):
        if self.from_block is not None:
            start = max(self.from_block, start)
        if self.to_block is not None:
            end = min(self.to_block, end)
        
        if start <= end:
            events = await self.event.get_logs(argument_filters=self.filter_args, fromBlock=start, toBlock=end)
            _logger.debug(f"Watcher {self.filter_id}: {len(events)} events from block {start} to block {end}")
            for event in events:
                _logger.debug(f"Watcher {self.filter_id}: watch event: {event}")
                tg.start_soon(wrap_callback(self.callback), event)


class EventWatcher(object):
    def __init__(
        self, w3: AsyncWeb3) -> None:
        self.w3 = w3
        self.page_size = 500

        self._event_filters: Dict[int, EventFilter] = {}
        self._next_filter_id: int = 0

        self._contracts: Dict[str, AsyncContract] = {}

        self._cache: Optional[BlockNumberCache] = None

        self._cancel_scope: Optional[CancelScope] = None

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

    def get_blocknumber_cache(self):
        return self._cache

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

        filter_id = self._next_filter_id
        event_filter = EventFilter(
            filter_id=filter_id,
            event=event,
            callback=callback,
            filter_args=filter_args,
            from_block=from_block,
            to_block=to_block,
        )
        self._event_filters[filter_id] = event_filter
        self._next_filter_id += 1
        _logger.debug(f"Add event watcher {contract_name}.{event_name}, {filter_args}")
        return filter_id

    def unwatch_event(self, filter_id: int):
        if filter_id in self._event_filters:
            event_filter = self._event_filters.pop(filter_id)
            _logger.debug(f"Remove event watcher {event_filter.event.event_name}")

    async def start(
        self,
        from_block: int = 0,
        to_block: int = 0,
        interval: float = 1,
    ):
        """
        watch events from block

        from_block: a block number, zero means start from the latest block
        to_block: a block number, zero means watch infinitely
        interval: sleep time, sleep when there is no new block
        """
        assert (
            self._cancel_scope is None
        ), "The watcher has already started. You should stop the watcher before restart it."

        try:
            self._cancel_scope = CancelScope()

            with self._cancel_scope:
                if from_block == 0:
                    if self._cache is not None:
                        from_block = await self._cache.get()
                        if from_block == 0:
                            from_block = await self.w3.eth.get_block_number()
                    else:
                        from_block = await self.w3.eth.get_block_number()
                    from_block += 1
                else:
                    if self._cache is not None:
                        await self._cache.set(from_block - 1)

                while to_block <= 0 or from_block <= to_block:
                    latest_blocknum = await self.w3.eth.get_block_number()
                    if from_block <= latest_blocknum:
                        end = min(latest_blocknum, from_block + self.page_size)
                        if len(self._event_filters) > 0:
                            async with create_task_group() as tg:
                                # fix event filters, avoid raise RuntimeError: dictionary changed size during iteration
                                event_filters = list(self._event_filters.values())
                                for event_filter in event_filters:
                                    await event_filter.process_events(start=from_block, end=end, tg=tg)
                        _logger.debug(f"Process events from block {from_block} to {end}")

                        with fail_after(delay=5, shield=True):
                            if self._cache is not None:
                                await self._cache.set(end)
                        from_block = end + 1
                    else:
                        await sleep(interval)
        finally:
            self._cancel_scope = None

    def stop(self):
        if self._cancel_scope is not None and not self._cancel_scope.cancel_called:
            self._cancel_scope.cancel()
