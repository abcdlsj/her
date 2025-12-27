"""Event type definitions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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


@dataclass
class ExploreStartEvent(Event):
    """Exploration started for a source."""

    source_name: str = ""


@dataclass
class ExploreEndEvent(Event):
    """Exploration completed for a source."""

    source_name: str = ""
    item_count: int = 0
    success: bool = True
    error: str | None = None


@dataclass
class DiscoveryEvent(Event):
    """Her found something interesting to share."""

    title: str = ""
    url: str = ""
    source: str = ""
    reason: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ChatEvent(Event):
    """Chat message event."""

    role: str = ""  # "user" or "assistant"
    content: str = ""


@dataclass
class ErrorEvent(Event):
    """Error occurred."""

    source: str = ""
    error: str = ""
    details: Any = None
