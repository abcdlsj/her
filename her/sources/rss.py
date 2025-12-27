"""RSS feed source."""

import asyncio
from datetime import datetime
from time import mktime

import feedparser

from her.sources.base import BaseSource, Item


class RSSSource(BaseSource):
    """Fetch items from RSS feeds."""

    def __init__(self, name: str, feed_urls: list[str]):
        super().__init__(name)
        self.feed_urls = feed_urls

    async def fetch(self) -> list[Item]:
        """Fetch items from all configured RSS feeds."""
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(None, self._parse_feed, url) for url in self.feed_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        items = []
        for result in results:
            if isinstance(result, list):
                items.extend(result)
        return items

    def _parse_feed(self, url: str) -> list[Item]:
        """Parse a single RSS feed."""
        feed = feedparser.parse(url)
        items = []

        for entry in feed.entries[:10]:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime.fromtimestamp(mktime(entry.published_parsed))

            summary = ""
            if hasattr(entry, "summary"):
                summary = entry.summary[:500] if len(entry.summary) > 500 else entry.summary

            items.append(
                Item(
                    title=entry.get("title", "Untitled"),
                    url=entry.get("link", ""),
                    source=self.name,
                    summary=summary,
                    published_at=published,
                    metadata={"feed_url": url},
                )
            )
        return items
