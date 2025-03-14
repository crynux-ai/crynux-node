import json
import logging
from asyncio import Queue
from datetime import datetime
import time
from typing import (Any, Awaitable, Callable, Dict, Generic, List, Optional,
                    TypeVar)

from anyio import (TASK_STATUS_IGNORED, CancelScope, Condition, create_memory_object_stream,
                   create_task_group, fail_after, get_cancelled_exc_class, move_on_after,
                   sleep)
from anyio.streams.memory import (MemoryObjectReceiveStream,
                                  MemoryObjectSendStream)
from anyio.abc import TaskGroup, TaskStatus
from eth_typing import ChecksumAddress
from hexbytes import HexBytes
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_fixed)
from web3.exceptions import BlockNotFound, TransactionNotFound
from web3.logs import DISCARD
from web3.types import BlockData, EventData, TxReceipt

from crynux_server.contracts import Contracts, ContractWrapper
from crynux_server.relay.abc import Relay
from crynux_server.relay.exceptions import RelayError
from crynux_server.models.chain_event import ChainEvent, ChainEventType, show_event_type

import httpx



ChainEventCallback = Callable[[ChainEvent], Awaitable[None]]

_logger = logging.getLogger(__name__)


def wrap_callback(callback: ChainEventCallback) -> ChainEventCallback:
    async def inner(event: ChainEvent):
        try:
            return await callback(event)
        except Exception as e:
            _logger.exception(e)
            _logger.error(f"Watcher callback for event {event} failed.")

    return inner

def _process_resp(resp: httpx.Response, method: str):
    try:
        resp.raise_for_status()
        return resp
    except httpx.HTTPStatusError as e:
        message = str(e)
        if resp.status_code == 400:
            try:
                content = resp.json()
                if "data" in content:
                    data = content["data"]
                    message = json.dumps(data)
                elif "message" in content:
                    message = content["message"]
                else:
                    message = resp.text
            except Exception:
                pass
        raise RelayError(resp.status_code, method, message) from e


# Filter events with a specific event type
# And process these events with a callback fucntion
class EventFilter(object):
    def __init__(
        self,
        filter_id: int,
        event_type: ChainEventType,
        callback: ChainEventCallback,
    ):
        self.filter_id = filter_id
        self.event_type = event_type
        self.callback = callback

    async def process_event(self, event: ChainEvent):
        if event.event_type == self.event_type:
            _logger.debug(f"Watcher {self.filter_id}: watch event: {event}")
            await wrap_callback(self.callback)(event)

# Watch all events related to node self.relay.node_address
# And manages all event filters to process these events
class EventWatcher(object):
    def __init__(
        self,
        base_url: str,
        relay: Relay,
        last_fetch_time: int = 0,
        fetch_interval: int = 5,
    ):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=30)
        self._relay = relay
        self._page_size = 20

        self._last_fetch_time = last_fetch_time
        self._fetch_interval = fetch_interval

        self._next_filter_id = 0
        self._event_filters: Dict[int, EventFilter] = {}

        self._cancel_scope: Optional[CancelScope] = None

    async def _fetch_events_once(
        self, event_sender: MemoryObjectSendStream[ChainEvent]
    ):
        start_time = self._last_fetch_time
        end_time = await self._relay.now()
        node_address = self._relay.node_address
        page_size = self._page_size

        input = {
            "start_time": start_time,
            "page": 1,
            "page_size": page_size,
            "end_time": end_time,
            "node_address": node_address,
        }
        while True:
            resp = await self._client.get("/v1/events", params=input)
            resp = _process_resp(resp, "getEvent")
            content = resp.json()
            data = content["data"]
            if len(data) == 0:
                break
            # Send the fetched events to the event_sender
            for event in data:
                chain_event = ChainEvent(
                    event_type=ChainEventType(event["type"]),
                    node_address=event["node_address"],
                    task_id_commitment=event["task_id_commitment"],
                    args=event["args"]
                )
                await event_sender.send(chain_event)
            input["page"] += 1

        _logger.info(
            f"fetched events for node {node_address} from {start_time} to {end_time}"
        )
        self._last_fetch_time = end_time
    
    # Fetch events evrey self._fetch_interval seconds
    # Send the fetched events to the event_sender
    # The _event_processor will process these events
    async def _event_fetcher(
        self, event_sender: MemoryObjectSendStream[ChainEvent]
    ):
        async with event_sender:
            while True:
                await self._fetch_events_once(event_sender)
                await sleep(self._fetch_interval)

    # Get events from event_receiver, which are send by the _event_fetcher
    # Process the events fetched one by one
    async def _event_processor(
        self, event_receiver: MemoryObjectReceiveStream[ChainEvent]
    ):
        async with event_receiver:
            async for event in event_receiver:
                _logger.info(f"Processing event: {event}")
                async with create_task_group() as tg:
                    event_filters = list(self._event_filters.values())
                    for event_filter in event_filters:
                        tg.start_soon(event_filter.process_event, event)

    # Add a filter to process events with a specific event type
    # The callback function will be called when the event is fetched
    def add_event_filter(
        self,
        event_type: ChainEventType,
        callback: ChainEventCallback,
    ):
        filter_id = self._next_filter_id
        self._next_filter_id += 1
        event_filter = EventFilter(
            filter_id=filter_id,
            event_type=event_type,
            callback=callback,
        )
        self._event_filters[filter_id] = event_filter
        _logger.debug(f"Add event filter for event type {show_event_type(event_type)}, filter id {filter_id}")
        return filter_id
    
    # Remove a filter to stop processing events with a specific event type
    def remove_event_filter(self, filter_id: int):
        if filter_id in self._event_filters:
            event_filter = self._event_filters.pop(filter_id)
            _logger.debug(f"Remove event filter for event type {show_event_type(event_filter.event_type)}")
    

    # Start the watcher
    # The watcher will fetch events and process these events
    async def start(self):
        assert (
            self._cancel_scope is None
        ), "The watcher has already started. You should stop the watcher before restart it."

        try:
            self._cancel_scope = CancelScope()

            with self._cancel_scope:
                # Prepare task status stream
                status_sender, status_receiver = create_memory_object_stream(
                    40, item_type=ChainEvent
                )

                async with create_task_group() as tg:
                    tg.start_soon(self._event_processor, status_receiver)
                    tg.start_soon(self._event_fetcher, status_sender)

        finally:
            self._cancel_scope = None

    # Stop the watcher
    async def stop(self):
        if self._cancel_scope is not None and not self._cancel_scope.cancel_called:
            self._cancel_scope.cancel()