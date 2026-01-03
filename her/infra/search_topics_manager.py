"""Search topics manager - manage search exploration topics.

Her can explore information through different methods:
- RSS (currently implemented)
- Web search (future)
- Local document search (future)

This module manages topics that Her will explore,
regardless of exploration method used.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

DEFAULT_TOPICS_FILE = Path.home() / ".her" / "search_topics.json"


@dataclass
class SearchTopic:
    """A search exploration topic."""

    id: str
    name: str
    description: str = ""
    method: str = "rss"
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "method": self.method,
            "config": self.config,
        }


@dataclass
class SearchTopicsConfig:
    """Configuration for search topics."""

    version: str = "1.0"
    topics: list[SearchTopic] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "topics": [t.to_dict() for t in self.topics],
        }


class SearchTopicsManager:
    """Manager for search topics with persistence."""

    def __init__(self, file_path: Path = DEFAULT_TOPICS_FILE):
        self.file_path = file_path
        self.config = self._load()

    def _load(self) -> SearchTopicsConfig:
        """Load configuration from file."""
        if not self.file_path.exists():
            return self._create_default()

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SearchTopicsConfig(
                version=data.get("version", "1.0"),
                topics=[SearchTopic(**t) for t in data.get("topics", [])],
            )
        except (json.JSONDecodeError, KeyError):
            return self._create_default()

    def _create_default(self) -> SearchTopicsConfig:
        """Create default configuration."""
        # Default: no topics, users can add them via conversation
        config = SearchTopicsConfig(topics=[])

        # Save directly
        config_data = config.to_dict()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        return config

    def save(self) -> None:
        """Save configuration to file."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)

    def get_all_topics(self) -> list[SearchTopic]:
        """Get all topics."""
        return self.config.topics.copy()

    def has_id(self, topic_id: str) -> bool:
        """Check if topic ID exists."""
        return any(t.id == topic_id for t in self.config.topics)

    def add_topic(
        self, topic_id: str, name: str, method: str = "rss", **kwargs
    ) -> tuple[bool, str]:
        """Add a new topic.

        Returns (success, message).
        """
        if self.has_id(topic_id):
            return False, f"话题已存在: {topic_id}"

        topic = SearchTopic(
            id=topic_id,
            name=name,
            description=kwargs.get("description", ""),
            method=method,
            config=kwargs.get("config", {}),
        )

        self.config.topics.append(topic)
        self.save()
        return True, f"已添加话题: {name}"

    def remove_topic(self, topic_id: str) -> tuple[bool, str]:
        """Remove a topic by ID.

        Returns (success, message).
        """
        for i, topic in enumerate(self.config.topics):
            if topic.id == topic_id:
                name = topic.name
                self.config.topics.pop(i)
                self.save()
                return True, f"已移除话题: {name}"

        return False, f"未找到话题: {topic_id}"

    def list_topics(self) -> str:
        """List all topics."""
        if not self.config.topics:
            return "当前没有搜索话题。"

        lines = ["当前搜索话题:"]
        for topic in self.config.topics:
            method_display = {
                "rss": "RSS",
                "web": "联网搜索",
                "local": "本地搜索",
            }.get(topic.method, topic.method)

            lines.append(f"  - [{topic.id}] {topic.name}")
            lines.append(f"    {topic.description}")
            lines.append(f"    方式: {method_display}")
            lines.append("")

        return "\n".join(lines)
