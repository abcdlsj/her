"""Event system for decoupled communication."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Event:
    """Base event class."""

    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def type(self) -> str:
        return self.__class__.__name__


@dataclass
class StatusEvent(Event):
    """Status update event."""
    message: str = ""


class EventBus:
    """Simple event bus for async communication."""

    def __init__(self, max_queue_size: int = 100):
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._max_queue_size = max_queue_size

    async def emit(self, event: Event) -> None:
        """Emit an event to all subscribers (non-blocking)."""
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> "Subscription":
        """Create a new subscription."""
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._max_queue_size)
        self._subscribers.append(queue)
        return Subscription(queue, self)

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        """Remove a subscriber."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)


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

    def close(self) -> None:
        """Close this subscription."""
        self._bus.unsubscribe(self._queue)
