"""Plugin base class and protocol for Her information sources."""

from abc import ABC, abstractmethod
from her.core.memory import Item


class Plugin(ABC):
    """Base class for Her plugins.

    Plugins provide information sources for Her to explore.
    Each plugin must implement the `fetch` method to return items.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name for identification."""

    @abstractmethod
    async def fetch(self) -> list[Item]:
        """Fetch items from the information source.

        Returns:
            List of items found.
        """

    def configure(self, config: dict) -> None:
        """Configure the plugin with settings.

        Args:
            config: Configuration dictionary.
        """
        pass

    async def close(self) -> None:
        """Clean up resources used by the plugin."""
        pass
