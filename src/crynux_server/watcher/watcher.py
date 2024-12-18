import logging
from asyncio import Queue
from datetime import datetime
from typing import (Any, Awaitable, Callable, Dict, Generic, List, Optional,
                    TypeVar)

from anyio import (TASK_STATUS_IGNORED, CancelScope, Condition,
                   create_task_group, get_cancelled_exc_class, move_on_after,
                   sleep)
from anyio.abc import TaskGroup, TaskStatus
from hexbytes import HexBytes
from web3.logs import DISCARD
from web3.types import EventData, TxReceipt, BlockData
from web3.exceptions import BlockNotFound, TransactionNotFound
from tenacity import retry, wait_fixed, stop_after_attempt, retry_if_exception_type

from crynux_server.contracts import Contracts, ContractWrapper

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


def _filter_event(
    event: EventData, filter_args: Optional[Dict[str, Any]] = None
) -> bool:
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
        events = await self.contract.event_process_receipt(
            self.event_name, receipt, errors=DISCARD
        )
        filtered_events = [
            event for event in events if _filter_event(event, self.filter_args)
        ]
        for event in filtered_events:
            _logger.debug(f"Watcher {self.filter_id}: watch event: {event}")
            await wrap_callback(self.callback)(event)

    async def process_events(self, block_receipts: List[TxReceipt], tg: TaskGroup):
        if len(block_receipts) == 0:
            return
        blocknum = block_receipts[0]["blockNumber"]
        filtered_events = []
        for receipt in block_receipts:
            events = await self.contract.event_process_receipt(
                self.event_name, receipt, errors=DISCARD
            )
            filtered_events.extend(
                [event for event in events if _filter_event(event, self.filter_args)]
            )
        _logger.debug(
            f"Watcher {self.filter_id}: {len(filtered_events)} events from block {blocknum}"
        )

        for event in filtered_events:
            _logger.debug(f"Watcher {self.filter_id}: watch event: {event}")
            tg.start_soon(wrap_callback(self.callback), event)


KT = TypeVar("KT")
VT = TypeVar("VT")


class CondMap(Generic[KT, VT]):
    def __init__(self) -> None:
        self._data: Dict[KT, VT] = {}
        self._cond = Condition()

    async def get(self, key: KT):
        async with self._cond:
            while key not in self._data:
                await self._cond.wait()
            return self._data[key]

    async def set(self, key: KT, value: VT):
        async with self._cond:
            self._data[key] = value
            self._cond.notify_all()


class EventWatcher(object):
    def __init__(self, contracts: Contracts):
        self.contracts = contracts

        self._event_filters: Dict[int, EventFilter] = {}
        self._next_filter_id: int = 0

        self._cancel_scope: Optional[CancelScope] = None

        self._blocknum_queue = Queue[int](100)
        self._tx_hash_queue = Queue[HexBytes](100)

        self._block_map = CondMap[int, BlockData]()
        self._tx_receipt_map = CondMap[HexBytes, TxReceipt]()


    @classmethod
    def from_contracts(cls, contracts: Contracts) -> "EventWatcher":
        assert contracts.initialized, "Contracts has not been initialized!"

        res = cls(contracts)
        return res

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

    @retry(
        wait=wait_fixed(3),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(BlockNotFound),
        reraise=True,
    )
    async def _get_block(self, blocknum: int):
        block = await self.contracts.get_block(blocknum)
        assert "transactions" in block
        with move_on_after(5, shield=True):
            for tx_hash in block["transactions"]:
                assert isinstance(tx_hash, bytes)
                await self._tx_hash_queue.put(tx_hash)
            await self._block_map.set(blocknum, block)
        assert "timestamp" in block
        blocktime = datetime.fromtimestamp(
            block["timestamp"]
        ).strftime("%Y-%m-%d %H:%M:%S")
        tx_count = len(block["transactions"])
        _logger.debug(
            f"get block {blocknum} produced at {blocktime}, {tx_count} txs"
        )

    async def _get_blocks(self):
        while True:
            blocknum = await self._blocknum_queue.get()
            try:
                await self._get_block(blocknum)
            except get_cancelled_exc_class():
                with move_on_after(1, shield=True):
                    await self._blocknum_queue.put(blocknum)
                raise
            except Exception:
                with move_on_after(1, shield=True):
                    await self._blocknum_queue.put(blocknum)
                raise
            
            self._blocknum_queue.task_done()

    @retry(
        wait=wait_fixed(3),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(TransactionNotFound),
        reraise=True,
    )
    async def _get_tx_receipt(self, tx_hash: HexBytes):
        receipt = await self.contracts.get_tx_receipt(tx_hash)
        await self._tx_receipt_map.set(tx_hash, receipt)
        blocknum = receipt["blockNumber"]
        tx_index = receipt["transactionIndex"]
        _logger.debug(
            f"get receipt {tx_index} of block {blocknum}"
        )

    async def _get_tx_receipts(self):
        while True:
            tx_hash = await self._tx_hash_queue.get()
            try:
                await self._get_tx_receipt(tx_hash)
            except get_cancelled_exc_class():
                with move_on_after(1, shield=True):
                    await self._tx_hash_queue.put(tx_hash)
                raise
            except Exception:
                with move_on_after(1, shield=True):
                    await self._tx_hash_queue.put(tx_hash)
                raise
            
            self._tx_hash_queue.task_done()

    async def _process_events(self, from_block: int, to_block: int):
        async with create_task_group() as tg:
            for blocknum in range(from_block, to_block + 1):
                block = await self._block_map.get(blocknum)
                assert "transactions" in block

                for tx_hash in block["transactions"]:
                    assert isinstance(tx_hash, bytes)
                    receipt = await self._tx_receipt_map.get(tx_hash)

                    event_filters = list(self._event_filters.values())
                    for event_filter in event_filters:
                        tg.start_soon(event_filter.process_receipt, receipt)

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
                async with create_task_group() as tg:
                    for _ in range(4):
                        tg.start_soon(self._get_blocks)

                    for _ in range(4):
                        tg.start_soon(self._get_tx_receipts)

                    if from_block == 0:
                        from_block = await self.contracts.get_current_block_number()
                    # signal the event watcher is started
                    task_status.started()

                    while to_block <= 0 or from_block <= to_block:
                        latest_blocknum = (
                            await self.contracts.get_current_block_number()
                        )
                        if from_block <= latest_blocknum:
                            tg.start_soon(self._process_events, from_block, latest_blocknum)

                            for blocknum in range(from_block, latest_blocknum + 1):
                                await self._blocknum_queue.put(blocknum)                            
                            from_block = latest_blocknum + 1

                        await sleep(interval)

                    await self._blocknum_queue.join()
                    await self._tx_hash_queue.join()

                    tg.cancel_scope.cancel()
        finally:
            self._cancel_scope = None

    def stop(self):
        if self._cancel_scope is not None and not self._cancel_scope.cancel_called:
            self._cancel_scope.cancel()
