"""Configuration management for Her."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_DIR = Path.home() / ".her"
DEFAULT_SOURCES_FILE = DEFAULT_CONFIG_DIR / "sources.toml"
BUILTIN_ROUTES_FILE = Path(__file__).parent / "data" / "rsshub_routes.toml"

DEFAULT_RSSHUB_INSTANCE = "https://rsshub.rssforever.com"


@dataclass
class SourceConfig:
    """Configuration for a single source."""

    name: str
    routes: list[str]
    enabled: bool = True
    source_type: str = "rsshub"
    instance: str = DEFAULT_RSSHUB_INSTANCE


@dataclass
class Config:
    """Her configuration."""

    rsshub_instance: str = DEFAULT_RSSHUB_INSTANCE
    sources: list[SourceConfig] = field(default_factory=list)
    routes_map: dict[str, list[str]] = field(default_factory=dict)


def load_routes_map() -> dict[str, list[str]]:
    """Load the built-in RSSHub routes map."""
    if not BUILTIN_ROUTES_FILE.exists():
        return {}

    try:
        with open(BUILTIN_ROUTES_FILE, "rb") as f:
            data = tomllib.load(f)
            return data.get("categories", {})
    except Exception:
        return {}


def load_config() -> Config:
    """Load configuration from files."""
    config = Config()
    config.routes_map = load_routes_map()

    if not DEFAULT_SOURCES_FILE.exists():
        config.sources = get_default_sources()
        save_sources(config.sources)
        return config

    try:
        with open(DEFAULT_SOURCES_FILE, "rb") as f:
            data = tomllib.load(f)

        config.rsshub_instance = data.get("rsshub", {}).get(
            "instance", DEFAULT_RSSHUB_INSTANCE
        )

        for src in data.get("sources", []):
            config.sources.append(
                SourceConfig(
                    name=src.get("name", "未命名"),
                    routes=src.get("routes", []),
                    enabled=src.get("enabled", True),
                    source_type=src.get("type", "rsshub"),
                    instance=src.get("instance", config.rsshub_instance),
                )
            )
    except Exception:
        config.sources = get_default_sources()

    return config


def get_default_sources() -> list[SourceConfig]:
    """Get default source configurations."""
    return [
        SourceConfig(
            name="热榜",
            routes=[
                "/v2ex/topics/hot",
                "/sspai/index",
                "/zhihu/hot",
            ],
        ),
        SourceConfig(
            name="科技",
            routes=[
                "/cnbeta",
                "/36kr/newsflashes",
                "/juejin/trending/all/weekly",
            ],
        ),
        SourceConfig(
            name="生活",
            routes=[
                "/douban/movie/weekly",
                "/bilibili/ranking/all/1/1",
            ],
        ),
    ]


def save_sources(sources: list[SourceConfig], instance: str = DEFAULT_RSSHUB_INSTANCE) -> None:
    """Save source configurations to file."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Her 信息源配置",
        "# 她会根据这个文件决定去哪里探索",
        "",
        "[rsshub]",
        f'instance = "{instance}"',
        "",
    ]

    for src in sources:
        lines.append("[[sources]]")
        lines.append(f'name = "{src.name}"')
        lines.append(f"enabled = {str(src.enabled).lower()}")
        if src.routes:
            routes_str = ", ".join(f'"{r}"' for r in src.routes)
            lines.append(f"routes = [{routes_str}]")
        else:
            lines.append("routes = []")
        lines.append("")

    with open(DEFAULT_SOURCES_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def add_route(source_name: str, route: str) -> bool:
    """Add a route to a source. Returns True if successful."""
    config = load_config()

    for src in config.sources:
        if src.name == source_name:
            if route not in src.routes:
                src.routes.append(route)
                save_sources(config.sources, config.rsshub_instance)
                return True
            return False

    config.sources.append(
        SourceConfig(name=source_name, routes=[route])
    )
    save_sources(config.sources, config.rsshub_instance)
    return True


def remove_route(source_name: str, route: str) -> bool:
    """Remove a route from a source. Returns True if successful."""
    config = load_config()

    for src in config.sources:
        if src.name == source_name and route in src.routes:
            src.routes.remove(route)
            save_sources(config.sources, config.rsshub_instance)
            return True

    return False


def get_route_suggestions(topic: str) -> list[str]:
    """Get route suggestions for a topic from the routes map."""
    routes_map = load_routes_map()

    topic_lower = topic.lower()
    for category, routes in routes_map.items():
        if topic_lower in category.lower() or category.lower() in topic_lower:
            return routes

    all_routes = []
    for routes in routes_map.values():
        all_routes.extend(routes)
    return all_routes[:5]


def create_sources_from_config(config: Config | None = None):
    """Create Source instances from configuration."""
    from her.sources.rsshub import RSSHubSource

    if config is None:
        config = load_config()

    sources = []
    for src in config.sources:
        if not src.enabled:
            continue
        if src.source_type == "rsshub":
            sources.append(
                RSSHubSource(
                    name=src.name,
                    routes=src.routes,
                    instance=src.instance,
                )
            )

    return sources
