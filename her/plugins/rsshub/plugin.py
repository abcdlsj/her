"""RSSHub plugin - complete RSS information source for Her.

RSSHub is a versatile RSS feed generator that can convert various platforms
(Weibo, Bilibili, Zhihu, Twitter, etc.) into RSS format.

Documentation: https://docs.rsshub.app
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import mktime
from typing import Any

import feedparser
import httpx

from her.core.memory import Item
from her.plugins.base import Plugin

DEFAULT_RSSHUB_INSTANCE = "https://rsshub.rssforever.com"
DEFAULT_SOURCES_FILE = Path.home() / ".her" / "rss_sources.json"


# === RSS Sources - Complete Collection ===

RSS_SOURCES_ALL = {
    "tech": [
        {
            "id": "sspai_matrix",
            "route": "/sspai/matrix",
            "name": "少数派 Matrix",
            "description": "少数派优质内容",
            "language": "zh-CN",
        },
        {
            "id": "v2ex_hot",
            "route": "/v2ex/topics/hot",
            "name": "V2EX 热门话题",
            "description": "V2EX 社区热门讨论",
            "language": "zh-CN",
        },
        {
            "id": "hackernews_best",
            "route": "/hackernews/best",
            "name": "Hacker News",
            "description": "Hacker News 精选",
            "language": "en",
        },
    ],
    "news": [
        {
            "id": "baidu_search_hot",
            "route": "/baidu/search/hot",
            "name": "百度热搜",
            "description": "百度搜索热词",
            "language": "zh-CN",
        },
    ],
    "social": [
        {
            "id": "bilibili_ranking",
            "route": "/bilibili/ranking/0/3",
            "name": "B站全站日榜",
            "description": "哔哩哔哩全站排行榜",
            "language": "zh-CN",
        },
    ],
    "finance": [
        {
            "id": "wallstreetcn_news",
            "route": "/wallstreetcn/news",
            "name": "华尔街见闻",
            "description": "华尔街见闻财经新闻",
            "language": "zh-CN",
        },
    ],
    "science": [
        {
            "id": "nature_research",
            "route": "/nature/research",
            "name": "Nature 研究",
            "description": "Nature 最新研究",
            "language": "en",
        },
    ],
}


def get_source_by_id(source_id: str) -> dict | None:
    """Find a source by its ID."""
    for category, sources in RSS_SOURCES_ALL.items():
        for source in sources:
            if source["id"] == source_id:
                return source
    return None


def format_sources_list(sources: list[dict]) -> str:
    """Format a list of sources for display."""
    lines = []
    for source in sources:
        lines.append(f"- [{source['id']}] {source['name']}")
        lines.append(f"  {source['description']}")
        lines.append(f"  路由: {source['route']}")
        lines.append("")
    return "\n".join(lines)


# === RSS Source Configuration ===


@dataclass
class RSSSource:
    """A single RSS source configuration."""

    id: str
    route: str
    name: str
    description: str = ""
    language: str = "en"
    category: str = "tech"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "route": self.route,
            "name": self.name,
            "description": self.description,
            "language": self.language,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RSSSource":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            route=data["route"],
            name=data["name"],
            description=data.get("description", ""),
            language=data.get("language", "en"),
            category=data.get("category", "tech"),
        )


@dataclass
class RSSHubConfig:
    """RSSHub configuration."""

    instance: str = DEFAULT_RSSHUB_INSTANCE
    sources: list[RSSSource] = field(default_factory=list)
    timeout: float = 30.0

    def get_routes(self) -> list[str]:
        """Get all routes."""
        return [s.route for s in self.sources]


# === RSSHub Plugin ===


class RSSHub(Plugin):
    """RSSHub plugin for Her.

    Provides:
    - Complete RSS source catalog (RSS_SOURCES_ALL)
    - Source management (add/remove/list)
    - Content fetching (fetch)
    """

    def __init__(
        self, config: RSSHubConfig | None = None, file_path: Path | None = None
    ):
        self.config = config or RSSHubConfig()
        self.file_path = file_path or DEFAULT_SOURCES_FILE
        self._client = httpx.AsyncClient(timeout=self.config.timeout)
        self._load()

    @property
    def name(self) -> str:
        return "RSSHub"

    def _load(self) -> None:
        """Load configuration from file."""
        if not self.file_path.exists():
            self._create_default()
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.config.sources = [
                RSSSource.from_dict(s) for s in data.get("sources", [])
            ]
        except (json.JSONDecodeError, KeyError):
            self._create_default()

    def _create_default(self) -> None:
        """Create default configuration with core sources."""
        default_source_ids = [
            "sspai_matrix",
            "v2ex_hot",
        ]

        default_sources = []
        for source_id in default_source_ids:
            source = get_source_by_id(source_id)
            if source:
                default_sources.append(
                    RSSSource(
                        id=source["id"],
                        route=source["route"],
                        name=source["name"],
                        description=source.get("description", ""),
                        language=source.get("language", "en"),
                        category=source.get("category", "tech"),
                    )
                )

        self.config.sources = default_sources
        self._save()

    def _save(self) -> None:
        """Save configuration to file."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "sources": [s.to_dict() for s in self.config.sources],
        }
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def configure(self, config: dict) -> None:
        """Configure the plugin with settings."""
        if "instance" in config:
            self.config.instance = config["instance"]
        if "timeout" in config:
            self.config.timeout = config["timeout"]

    def get_current_routes(self) -> list[str]:
        """Get currently enabled routes."""
        return self.config.get_routes()

    def get_all_sources(self) -> list[RSSSource]:
        """Get all enabled sources."""
        return self.config.sources.copy()

    def has_id(self, source_id: str) -> bool:
        """Check if source ID exists."""
        return any(s.id == source_id for s in self.config.sources)

    def add_source(
        self, source_id: str, route: str, name: str, **kwargs
    ) -> tuple[bool, str]:
        """Add a new source.

        Returns (success, message).
        """
        source = RSSSource(id=source_id, route=route, name=name, **kwargs)

        if self.has_id(source_id):
            return False, f"源已存在: {source_id}"

        self.config.sources.append(source)
        self._save()
        return True, f"已添加: {name}"

    def remove_source(self, source_id: str) -> tuple[bool, str]:
        """Remove a source by ID.

        Returns (success, message).
        """
        source = None
        for i, s in enumerate(self.config.sources):
            if s.id == source_id:
                source = s
                self.config.sources.pop(i)
                self._save()
                return True, f"已移除: {source.name}"

        return False, f"未找到源: {source_id}"

    def list_sources(self, category: str | None = None) -> str:
        """List all enabled sources."""
        sources = self.config.sources
        if category:
            sources = [s for s in sources if s.category == category]

        if not sources:
            return "当前没有启用任何 RSS 源。"

        lines = ["当前启用的 RSS 源:"]
        for source in sources:
            lines.append(f"  - [{source.id}] {source.name}")
            lines.append(f"    {source.description}")
            lines.append(f"    类别: {source.category}, 语言: {source.language}")
            lines.append("")
        return "\n".join(lines)

    def get_source_by_id(self, source_id: str) -> RSSSource | None:
        """Get source by ID."""
        for s in self.config.sources:
            if s.id == source_id:
                return s
        return None

    async def fetch(self) -> list[Item]:
        """Fetch items from all configured routes."""
        routes = self.config.get_routes()
        if not routes:
            return []

        tasks = [self._fetch_route(route) for route in routes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        items = []
        for result in results:
            if isinstance(result, list):
                items.extend(result)

        return items

    async def _fetch_route(self, route: str) -> list[Item]:
        """Fetch items from a single route."""
        url = self._build_url(route)

        try:
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, url)

            items = []
            for entry in feed.entries[:10]:
                published = None
                if (
                    hasattr(entry, "published_parsed")
                    and entry.published_parsed
                    and isinstance(entry.published_parsed, tuple)
                ):
                    published = datetime.fromtimestamp(mktime(entry.published_parsed))

                summary = ""
                if hasattr(entry, "summary") and entry.summary:
                    summary = (
                        entry.summary[:500]
                        if len(entry.summary) > 500
                        else entry.summary
                    )

                score = 0
                if hasattr(entry, "score") and entry.score:
                    score = int(entry.score)

                title = (
                    entry.get("title", "Untitled")
                    if isinstance(entry.get("title"), str)
                    else "Untitled"
                )
                url_value = (
                    entry.get("link", "") if isinstance(entry.get("link"), str) else ""
                )

                items.append(
                    Item(
                        title=title,
                        url=url_value,
                        source=f"RSSHub:{route}",
                        summary=summary,
                        published_at=published,
                        metadata={"route": route, "score": score},
                    )
                )

            return items

        except Exception:
            return []

    def _build_url(self, route: str) -> str:
        """Build full URL from route."""
        instance = self.config.instance.rstrip("/")
        route = route if route.startswith("/") else f"/{route}"
        return f"{instance}{route}"

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()


def create_rsshub(
    file_path: Path | None = None,
    instance: str = DEFAULT_RSSHUB_INSTANCE,
) -> RSSHub:
    """Create an RSSHub plugin with default configuration."""
    config = RSSHubConfig(instance=instance)
    return RSSHub(config=config, file_path=file_path)
