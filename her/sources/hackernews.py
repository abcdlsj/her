"""Hacker News source."""

import asyncio
from datetime import datetime

import httpx

from her.sources.base import BaseSource, Item

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsSource(BaseSource):
    """Fetch top stories from Hacker News."""

    def __init__(self, limit: int = 20):
        super().__init__("Hacker News")
        self.limit = limit

    async def fetch(self) -> list[Item]:
        """Fetch top stories from HN."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{HN_API_BASE}/topstories.json")
            story_ids = resp.json()[: self.limit]

            tasks = [self._fetch_story(client, story_id) for story_id in story_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            return [r for r in results if isinstance(r, Item)]

    async def _fetch_story(self, client: httpx.AsyncClient, story_id: int) -> Item:
        """Fetch a single story."""
        resp = await client.get(f"{HN_API_BASE}/item/{story_id}.json")
        data = resp.json()

        return Item(
            title=data.get("title", "Untitled"),
            url=data.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
            source=self.name,
            summary=f"Score: {data.get('score', 0)} | Comments: {data.get('descendants', 0)}",
            published_at=datetime.fromtimestamp(data.get("time", 0)),
            metadata={
                "hn_id": story_id,
                "score": data.get("score", 0),
                "comments": data.get("descendants", 0),
                "by": data.get("by", "unknown"),
            },
        )
