# sources/ - 信息源模块

## 职责

提供各种信息源的统一抽象，让 Her 能够从不同平台获取信息。

## Source 接口

所有信息源必须实现 `Source` 协议：

```python
class Source(Protocol):
    name: str  # 源名称，如 "Hacker News"

    async def fetch(self) -> list[Item]:
        """获取信息列表"""
        ...
```

## Item 数据结构

```python
@dataclass
class Item:
    title: str                      # 标题
    url: str                        # 链接
    source: str                     # 来源名称
    summary: str = ""               # 摘要
    published_at: datetime | None   # 发布时间
    metadata: dict                  # 额外信息
```

## 已实现的源

| 源 | 文件 | 说明 |
|----|------|------|
| Hacker News | `hackernews.py` | HN API 获取热门文章 |
| RSS | `rss.py` | 通用 RSS 订阅 |

## 添加新源

1. 创建文件 `her/sources/xxx.py`
2. 继承 `BaseSource` 或实现 `Source` 协议
3. 实现 `async def fetch(self) -> list[Item]`
4. 在 `__init__.py` 中导出

示例：

```python
# her/sources/twitter.py
from her.sources.base import BaseSource, Item

class TwitterSource(BaseSource):
    def __init__(self, keywords: list[str]):
        super().__init__("Twitter")
        self.keywords = keywords

    async def fetch(self) -> list[Item]:
        # 实现获取逻辑
        ...
```

## 注意事项

- `fetch()` 必须是异步的
- 做好错误处理，网络问题不应该崩溃
- 限制返回数量，避免信息过载
- metadata 用于存储源特有的信息
