"""Event bus implementation."""

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

from her.events.types import Event


class EventBus:
    """
    Simple event bus for async communication.

    Supports:
    - Multiple subscribers
    - Event type filtering
    - Non-blocking emit
    """

    def __init__(self, max_queue_size: int = 100):
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._handlers: dict[type[Event], list[Callable]] = {}
        self._max_queue_size = max_queue_size

    async def emit(self, event: Event) -> None:
        """
        Emit an event to all subscribers.

        Non-blocking: if a subscriber's queue is full, the event is dropped for that subscriber.
        """
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

    def subscribe(self) -> "Subscription":
        """
        Create a new subscription.

        Returns a Subscription that can be used as an async iterator.
        """
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._max_queue_size)
        self._subscribers.append(queue)
        return Subscription(queue, self)

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        """Remove a subscriber."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def on(self, event_type: type[Event], handler: Callable[[Event], Any]) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def off(self, event_type: type[Event], handler: Callable[[Event], Any]) -> None:
        """Remove a handler."""
        if event_type in self._handlers:
            handlers = self._handlers[event_type]
            if handler in handlers:
                handlers.remove(handler)


class Subscription:
    """A subscription to the event bus."""

    def __init__(self, queue: asyncio.Queue[Event], bus: EventBus):
        self._queue = queue
        self._bus = bus

    async def __aiter__(self) -> AsyncIterator[Event]:
        """Iterate over events."""
        try:
            while True:
                event = await self._queue.get()
                yield event
        finally:
            self._bus.unsubscribe(self._queue)

    async def get(self, timeout: float | None = None) -> Event | None:
        """Get next event with optional timeout."""
        try:
            if timeout is not None:
                return await asyncio.wait_for(self._queue.get(), timeout)
            return await self._queue.get()
        except asyncio.TimeoutError:
            return None

    def get_nowait(self) -> Event | None:
        """Get event without waiting, returns None if empty."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def close(self) -> None:
        """Close this subscription."""
        self._bus.unsubscribe(self._queue)
