import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Dict, List, Optional

from anyio import (CancelScope, create_memory_object_stream, create_task_group,
                   sleep)
from anyio.streams.memory import (MemoryObjectReceiveStream,
                                  MemoryObjectSendStream)

from crynux_server.models import Event, EventType
from crynux_server.relay import Relay
from crynux_server.relay.abc import Relay

EventCallback = Callable[[Event], Awaitable[None]]

_logger = logging.getLogger(__name__)


def wrap_callback(callback: EventCallback) -> EventCallback:
    async def inner(event: Event):
        try:
            return await callback(event)
        except Exception as e:
            _logger.exception(e)
            _logger.error(f"Watcher callback for event {event} failed.")

    return inner


# Filter events with a specific event type
# And process these events with a callback fucntion
class EventFilter(object):
    def __init__(
        self,
        filter_id: int,
        event_type: EventType,
        callback: EventCallback,
    ):
        self.filter_id = filter_id
        self.event_type = event_type
        self.callback = callback

    async def process_event(self, event: Event):
        _logger.debug(f"Watcher {self.filter_id}: watch event: {event}")
        await wrap_callback(self.callback)(event)


# Watch all events related to node self.relay.node_address
# And manages all event filters to process these events
class EventWatcher(object):
    def __init__(
        self,
        relay: Relay,
        fetch_interval: int = 1,
    ):
        self._relay = relay

        self._last_fetch_time = datetime.now()
        self._fetch_interval = fetch_interval

        self._next_filter_id = 0
        self._event_filters: Dict[EventType, Dict[int, EventFilter]] = defaultdict(dict)
        self._filter_types: Dict[int, EventType] = {}

        self._cancel_scope: Optional[CancelScope] = None

    async def _fetch_events(self) -> List[Event]:
        start_time = self._last_fetch_time
        end_time = datetime.now()
        page = 1
        page_size = 50

        all_events = []
        while True:
            events = await self._relay.get_events(
                start_time=start_time,
                end_time=end_time,
                node_address=self._relay.node_address,
                page=page,
                page_size=page_size,
            )
            if len(events) < page_size:
                break
            all_events.extend(events)
            page += 1

        _logger.debug(
            f"fetched events for node {self._relay.node_address} from {start_time} to {end_time}"
        )
        self._last_fetch_time = end_time
        return all_events

    # Fetch events evrey self._fetch_interval seconds
    # Send the fetched events to the event_sender
    # The _event_processor will process these events
    async def _event_fetcher(self, event_sender: MemoryObjectSendStream[Event]):
        async with event_sender:
            while True:
                events = await self._fetch_events()
                for event in events:
                    await event_sender.send(event)
                await sleep(self._fetch_interval)

    # Get events from event_receiver, which are send by the _event_fetcher
    # Process the events fetched one by one
    async def _event_processor(self, event_receiver: MemoryObjectReceiveStream[Event]):
        async with event_receiver:
            async for event in event_receiver:
                _logger.debug(f"Processing event: {event}")
                async with create_task_group() as tg:
                    event_filters = self._event_filters[event.type].values()
                    for event_filter in event_filters:
                        tg.start_soon(event_filter.process_event, event)

    # Add a filter to process events with a specific event type
    # The callback function will be called when the event is fetched
    def add_event_filter(
        self,
        event_type: EventType,
        callback: EventCallback,
    ):
        filter_id = self._next_filter_id
        self._next_filter_id += 1
        event_filter = EventFilter(
            filter_id=filter_id,
            event_type=event_type,
            callback=callback,
        )
        self._event_filters[event_type][filter_id] = event_filter
        self._filter_types[filter_id] = event_type
        _logger.debug(
            f"Add event filter for event type {event_type}, filter id {filter_id}"
        )
        return filter_id

    # Remove a filter to stop processing events with a specific event type
    def remove_event_filter(self, filter_id: int):
        if filter_id in self._filter_types:
            filter_type = self._filter_types.pop(filter_id)
            self._event_filters[filter_type].pop(filter_id)
            _logger.debug(f"Remove event filter {filter_id} of type {filter_type}")

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
                    40, item_type=Event
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
