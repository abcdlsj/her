"""Base classes for information sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass
class Item:
    """A piece of information from a source."""

    title: str
    url: str
    source: str
    summary: str = ""
    published_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    def __str__(self) -> str:
        time_str = self.published_at.strftime("%Y-%m-%d %H:%M") if self.published_at else "unknown"
        return f"[{self.source}] {self.title} ({time_str})"


@runtime_checkable
class Source(Protocol):
    """Protocol for information sources."""

    name: str

    async def fetch(self) -> list[Item]:
        """Fetch items from the source."""
        ...


class BaseSource(ABC):
    """Base class for implementing sources."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def fetch(self) -> list[Item]:
        """Fetch items from the source."""
        pass
