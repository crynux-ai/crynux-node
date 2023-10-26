import logging
from typing import Any, Awaitable, Callable, Dict, Optional, cast

from anyio import CancelScope, Event, create_task_group, fail_after, sleep
from anyio.abc import TaskGroup
from tenacity import (AsyncRetrying, before_sleep_log, stop_after_attempt,
                      wait_fixed)
from web3 import AsyncWeb3
from web3.contract.async_contract import AsyncContract, AsyncContractEvent
from web3.types import EventData

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

    async def process_events(self, start: int, end: int, tg: TaskGroup):
        if self.from_block is not None:
            start = max(self.from_block, start)
        if self.to_block is not None:
            end = min(self.to_block, end)
        
        if start <= end:
            events = await self.event.get_logs(argument_filters=self.filter_args, fromBlock=start, toBlock=end)
            for event in events:
                _logger.debug(f"Watch event: {event}")
                tg.start_soon(wrap_callback(self.callback), event)


class EventWatcher(object):
    def __init__(
        self, w3: AsyncWeb3, retry_count: int = 3, retry_delay: float = 10
    ) -> None:
        self.w3 = w3
        self.page_size = 500
        self.retry_count = retry_count
        self.retry_delay = retry_delay

        self._event_filters: Dict[int, EventFilter] = {}
        self._next_filter_id: int = 0

        self._contracts: Dict[str, AsyncContract] = {}

        self._cache: Optional[BlockNumberCache] = None

        self._cancel_scope: Optional[CancelScope] = None
        self._stop_event: Optional[Event] = None

    @classmethod
    def from_contracts(cls, contracts: Contracts, retry_count: int = 3, retry_delay: float = 10) -> "EventWatcher":
        assert contracts.initialized, "Contracts has not been initialized!"

        res = cls(contracts.w3, retry_count=retry_count, retry_delay=retry_delay)
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
            event_filter = self._event_filters.pop(filter_id)
            _logger.debug(f"Unwatch event {event_filter.event.event_name}")

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

        async for attemp in AsyncRetrying(
            stop=stop_after_attempt(self.retry_count),
            wait=wait_fixed(self.retry_delay),
            before_sleep=before_sleep_log(_logger, logging.ERROR, exc_info=True),
            reraise=True,
        ):
            with attemp:

                try:
                    self._cancel_scope = CancelScope()
                    self._stop_event = Event()

                    with self._cancel_scope:
                        if from_block is None:
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

                        def _should_stop(stop_event: Event, start: int):
                            if stop_event.is_set():
                                return True
                            if to_block is None:
                                return False
                            return start > to_block

                        while not _should_stop(self._stop_event, from_block):
                            latest_blocknum = await self.w3.eth.get_block_number()
                            if from_block <= latest_blocknum:
                                end = min(latest_blocknum, from_block + self.page_size)
                                if len(self._event_filters) > 0:
                                    async with create_task_group() as tg:
                                        for event_filter in self._event_filters.values():
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
                    self._stop_event = None

    def stop(self):
        if self._stop_event is not None:
            self._stop_event.set()
        if self._cancel_scope is not None and not self._cancel_scope.cancel_called:
            self._cancel_scope.cancel()
