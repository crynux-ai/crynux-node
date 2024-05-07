import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from anyio import CancelScope, TASK_STATUS_IGNORED, create_task_group, fail_after, sleep
from anyio.abc import TaskGroup, TaskStatus
from web3.types import EventData

from crynux_server.contracts import Contracts, ContractWrapper

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
        contract: ContractWrapper,
        event_name: str,
        callback: EventCallback,
        filter_args: Optional[Dict[str, Any]] = None,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
    ):
        self.filter_id = filter_id
        self.contract = contract
        self.event_name = event_name
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
            events = await self.contract.get_events(event_name=self.event_name, filter_args=self.filter_args, from_block=start, to_block=end)
            _logger.debug(f"Watcher {self.filter_id}: {len(events)} events from block {start} to block {end}")
            for event in events:
                _logger.debug(f"Watcher {self.filter_id}: watch event: {event}")
                tg.start_soon(wrap_callback(self.callback), event)


class EventWatcher(object):
    def __init__(self, contracts: Contracts):
        self.contracts = contracts
        self.page_size = 500

        self._event_filters: Dict[int, EventFilter] = {}
        self._next_filter_id: int = 0

        self._cache: Optional[BlockNumberCache] = None

        self._cancel_scope: Optional[CancelScope] = None

    @classmethod
    def from_contracts(cls, contracts: Contracts) -> "EventWatcher":
        assert contracts.initialized, "Contracts has not been initialized!"

        res = cls(contracts)
        return res

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
        contract = self.contracts.get_contract(contract_name)

        filter_id = self._next_filter_id
        event_filter = EventFilter(
            filter_id=filter_id,
            contract=contract,
            event_name=event_name,
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
            _logger.debug(f"Remove event watcher {event_filter.event_name}")

    async def start(
        self,
        from_block: int = 0,
        to_block: int = 0,
        interval: float = 1,
        *,
        task_status: TaskStatus[None] = TASK_STATUS_IGNORED,
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
                            from_block = await self.contracts.get_current_block_number()
                    else:
                        from_block = await self.contracts.get_current_block_number()
                    from_block += 1
                else:
                    if self._cache is not None:
                        await self._cache.set(from_block - 1)
                # signal the event watcher is started
                task_status.started()

                while to_block <= 0 or from_block <= to_block:
                    latest_blocknum = await self.contracts.get_current_block_number()
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
