import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from anyio import (TASK_STATUS_IGNORED, CancelScope, CapacityLimiter,
                   create_memory_object_stream, create_task_group, fail_after,
                   sleep)
from anyio.abc import (ObjectReceiveStream, ObjectSendStream, TaskGroup,
                       TaskStatus)
from hexbytes import HexBytes
from web3.logs import DISCARD
from web3.types import EventData, TxReceipt

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


def _filter_event(event: EventData, filter_args: Optional[Dict[str, Any]] = None) -> bool:
    if filter_args is None:
        return True
    for key, val in filter_args.items():
        if key in event["args"]:
            real_val = event["args"][key]
            if real_val != val:
                return False
    return True


class EventFilter(object):
    def __init__(
        self,
        filter_id: int,
        contract: ContractWrapper,
        event_name: str,
        callback: EventCallback,
        filter_args: Optional[Dict[str, Any]] = None,
    ):
        self.filter_id = filter_id
        self.contract = contract
        self.event_name = event_name
        self.callback = callback
        self.filter_args = filter_args

    async def process_receipt(self, receipt: TxReceipt):
        events = await self.contract.event_process_receipt(self.event_name, receipt, errors=DISCARD)
        filtered_events = [event for event in events if _filter_event(event, self.filter_args)]
        for event in filtered_events:
            _logger.debug(f"Watcher {self.filter_id}: watch event: {event}")
            await wrap_callback(self.callback)(event)

    async def process_events(self, block_receipts: List[TxReceipt], tg: TaskGroup):
        if len(block_receipts) == 0:
            return
        blocknum = block_receipts[0]["blockNumber"]
        filtered_events = []
        for receipt in block_receipts:
            events = await self.contract.event_process_receipt(self.event_name, receipt, errors=DISCARD)
            filtered_events.extend([event for event in events if _filter_event(event, self.filter_args)])
        _logger.debug(f"Watcher {self.filter_id}: {len(filtered_events)} events from block {blocknum}")

        for event in filtered_events:
            _logger.debug(f"Watcher {self.filter_id}: watch event: {event}")
            tg.start_soon(wrap_callback(self.callback), event)


class EventWatcher(object):
    def __init__(self, contracts: Contracts):
        self.contracts = contracts

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
    ) -> int:
        contract = self.contracts.get_contract(contract_name)

        filter_id = self._next_filter_id
        event_filter = EventFilter(
            filter_id=filter_id,
            contract=contract,
            event_name=event_name,
            callback=callback,
            filter_args=filter_args,
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

                tx_hashes_sender, tx_hashes_receiver = create_memory_object_stream(100, item_type=HexBytes)

                async def _process_block(sender: ObjectSendStream[HexBytes], blocknum: int, limiter: CapacityLimiter):
                    async with limiter:
                        block = await self.contracts.get_block(blocknum)
                        assert "transactions" in block
                        for tx_hash in block["transactions"]:
                            assert isinstance(tx_hash, bytes)
                            await sender.send(tx_hash)
                        assert "timestamp" in block
                        blocktime = datetime.fromtimestamp(block["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                        _logger.debug(f"get block {blocknum} produced at {blocktime}")


                async def _process_blocks(sender: ObjectSendStream[HexBytes], from_block: int, to_block: int):
                    if from_block == 0:
                        if self._cache is not None:
                            from_block = await self._cache.get()
                            if from_block == 0:
                                from_block = await self.contracts.get_current_block_number()
                        else:
                            from_block = await self.contracts.get_current_block_number()
                    else:
                        if self._cache is not None:
                            await self._cache.set(from_block)
                    # signal the event watcher is started
                    task_status.started()

                    limiter = CapacityLimiter(4)
                    async with sender:
                        async with create_task_group() as tg:
                            while to_block <= 0 or from_block <= to_block:
                                latest_blocknum = await self.contracts.get_current_block_number()
                                while from_block <= latest_blocknum:
                                    tg.start_soon(_process_block, sender, from_block, limiter)
                                    from_block += 1
                                with fail_after(delay=5, shield=True):
                                    if self._cache is not None:
                                        await self._cache.set(from_block)
                                await sleep(interval)


                async def _process_tx_receipt(receiver: ObjectReceiveStream[HexBytes]):
                    async with receiver:
                        async with create_task_group() as tg:
                            async for tx_hash in receiver:
                                receipt = await self.contracts.get_tx_receipt(tx_hash)
                                event_filters = list(self._event_filters.values())
                                for event_filter in event_filters:
                                    tg.start_soon(event_filter.process_receipt, receipt)
                
                async with create_task_group() as tg:
                    tg.start_soon(_process_blocks, tx_hashes_sender, from_block, to_block)

                    for _ in range(4):
                        tg.start_soon(_process_tx_receipt, tx_hashes_receiver.clone())
                    
                    tx_hashes_receiver.close()
        finally:
            self._cancel_scope = None

    def stop(self):
        if self._cancel_scope is not None and not self._cancel_scope.cancel_called:
            self._cancel_scope.cancel()
