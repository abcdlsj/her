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
class ThinkingEvent(Event):
    """Her is thinking - show playful inner monologue."""

    thought: str = ""


@dataclass
class FetchingEvent(Event):
    """Data fetching in progress."""

    source: str = ""
    progress: float = 0.0


@dataclass
class NewDataEvent(Event):
    """New data available from background fetch."""

    source: str = ""
    count: int = 0


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

    role: str = ""
    content: str = ""


@dataclass
class ErrorEvent(Event):
    """Error occurred."""

    source: str = ""
    error: str = ""
    details: Any = None


@dataclass
class SourceModifiedEvent(Event):
    """Source configuration was modified."""

    action: str = ""
    source_name: str = ""
    route: str | None = None
