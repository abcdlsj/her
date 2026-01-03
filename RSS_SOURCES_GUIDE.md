# RSS 源管理指南

## 概述

Her 的探索能力采用**多层架构**：

1. **RSS 源**：用户可以通过对话配置，持久化到文件
2. **搜索话题**：Her 主导管理，用于探索不同方向

RSS 对 Her 来说只是**探索的一种方式**，不是用户的直接配置项。未来扩展：
- 联网搜索
- 本地文档搜索
- 其他探索方式

## 目录结构

```
her/infra/
├── rss_sources_manager.py      # RSS 源管理（用户配置）
├── rss_sources_all.py           # RSS 源全集（27 个验证通过的源）
└── search_topics_manager.py  # 搜索话题管理（Her 管理）
```

## RSS 源管理

### 用户操作

用户可以以下方式管理 RSS 源：
- 添加源："增加 RSS 源 知乎热榜"
- 删除源："删除 RSS 源 知乎热榜"
- 查看源："查看 RSS 源"

Her 会智能理解并执行这些操作。

### 配置持久化

- 存储位置：`~/.her/rss_sources.json`
- 默认启用 4 个核心源（科技+新闻+社交）
- 格式：JSON

## 搜索话题管理

### Her 的自主行为

Her 根据对话上下文，自主管理搜索话题：
- **增加话题**：发现用户对某话题感兴趣，主动添加到搜索列表
- **删除话题**：认为某话题不再相关，主动从列表中移除
- **列出示话题**：用户可以查看当前搜索话题

### 搜索话题数据结构

```python
{
  "id": "tech_news",
  "name": "科技新闻",
  "description": "科技综合新闻",
  "method": "rss",  # rss/web/local
  "config": {}
}
```

### 使用方式

#### 用户方式（对话）
```
用户：增加搜索话题 人工智能
Her：已添加话题：人工智能（RSS）

用户：查看搜索话题
Her：当前搜索话题：
  - [tech_news] 科技新闻（RSS）
  - [ai_trends] AI 趋势（RSS）
  ...
```

#### Her 自主行为
```
Her 思考：用户最近一直在询问 AI 相关问题，我可以添加这个话题
Her 生成自主意图：ADD_SEARCH_TOPIC
Her 执行：topics_manager.add_topic("ai_trends", "AI 趋势", "rss")
```

## 配置与意图的区分

### RSS 源（配置层）

- **性质**：配置项，用户通过对话管理
- **持久化**：独立 JSON 文件
- **用途**：作为探索的 RSS 源
- **管理方式**：通过对话命令

### 搜索话题（探索层）

- **性质**：Her 的自主决策
- **持久化**：独立 JSON 文件
- **用途**：Her 决定探索什么，如何探索
- **管理方式**：通过意图识别 + 自主决策

## 设计理念

### 配置 vs. 意图

| 特性 | RSS 源 | 搜索话题 |
|------|---------|----------|
| 管理者 | 用户 | Her（自主）|
| 存储 | JSON | JSON |
| 触发 | 对话命令 | 意图识别 |
| 目的 | 探索的信息源 | 探索的内容方向 |

## 当前实现

### RSS 源配置
- **默认源**：4 个（从 27 个验证通过的源中选择）
- **可用源**：7 个（验证通过）

### 搜索话题
- **默认话题**：无（Her 自主添加）
- **探索方式**：RSS（未来支持 Web/Local）

## API 参考

### RSS Sources Manager

```python
from her.infra.rss_sources_manager import RSSSourcesManager

manager = RSSSourcesManager()

# Get current routes
routes = manager.get_current_routes()

# Add source
success, message = manager.add_source(
    source_id="zhihu_hot",
    route="/zhihu/hot",
    name="知乎热榜",
    description="知乎今日热榜",
    language="zh-CN",
    category="news",
)

# Remove source
success, message = manager.remove_source("zhihu_hot")

# List sources
text = manager.list_sources()
```

### Search Topics Manager

```python
from her.infra.search_topics_manager import SearchTopicsManager

manager = SearchTopicsManager()

# Add topic
success, message = manager.add_topic(
    topic_id="ai_news",
    name="AI 新闻",
    method="rss",
    description="AI 相关新闻",
)

# Remove topic
success, message = manager.remove_topic("ai_news")

# List topics
text = manager.list_topics()
```

### 意图识别

```python
IntentType.ADD_SEARCH_TOPIC     # 增加搜索话题
IntentType.REMOVE_SEARCH_TOPIC  # 删除搜索话题
IntentType.LIST_SEARCH_TOPICS  # 列出示话题
```

### Agent 集成

```python
from her.core import Her
from her.infra.rss_sources_manager import RSSSourcesManager
from her.infra.search_topics_manager import SearchTopicsManager

# Create managers
rss_manager = RSSSourcesManager()
topics_manager = SearchTopicsManager()

# Create agent
agent = Her(
    llm=llm,
    rsshub=None,
    sources_manager=rss_manager,
    search_topics_manager=topics_manager,
)
```

## 测试

```bash
# 测试 RSS 源
uv run python -c "from her.infra.rss_sources_manager import RSSSourcesManager; RSSSourcesManager()"

# 测试搜索话题
uv run python -c "from her.infra.search_topics_manager import SearchTopicsManager; SearchTopicsManager()"

# 测试完整集成
uv run python -c "from her.core import Her; from her.infra.rss_sources_manager import RSSSourcesManager; ..."
```

## 未来扩展

### 联网搜索

```python
# User adds a web search topic
success, message = topics_manager.add_topic(
    topic_id="python_news",
    name="Python 新闻",
    method="web",  # 扩展方法
    description="Python 相关新闻",
)

# Her explores via web
await agent.explore_topic(topic_id)
```

### 本地文档搜索

```python
# User adds a local search topic
success, message = topics_manager.add_topic(
    topic_id="local_docs",
    name="本地文档",
    method="local",
    description="搜索我的文档",
)

# Her explores via local
await agent.explore_topic(topic_id)
```

## 配置说明

### RSS 源配置文件

位置：`~/.her/rss_sources.json`

默认内容：
```json
{
  "version": "1.0",
  "sources": [
    {
      "id": "sspai_matrix",
      "route": "/sspai/matrix",
      "name": "少数派 Matrix",
      "description": "少数派优质内容",
      "language": "zh-CN",
      "category": "tech"
    }
  ]
}
```

### 搜索话题配置文件

位置：`~/.her/search_topics.json`

默认内容：无（Her 自主添加）

示例内容：
```json
{
  "version": "1.0",
  "topics": [
    {
      "id": "ai_trends",
      "name": "AI 趋势",
      "description": "AI 相关新闻",
      "method": "rss",
      "config": {}
    }
  ]
}
```

## 注意事项

1. **RSS 源是配置**
   - 用户通过对话添加/删除
   - Her 用来探索（作为探索源）

2. **搜索话题是意图**
   - Her 根据对话上下文自主管理
   - 用户也可以主动添加/删除
   - Her 用来探索方向

3. **扩展方向**
   - RSS：当前只支持这一个探索方式
   - 未来：Web 搜索、本地文档搜索
   - 任何扩展都不影响 RSS 源的使用
her/infra/
├── rss_sources_all.py      # RSS 源全集（27 个源）
└── rss_sources_manager.py  # RSS 源管理器（持久化）
```

## 全集源（RSS_SOURCES_ALL）

### 类别

| 类别 | 源数 | 说明 |
|------|------|------|
| tech | 6 | 科技新闻和更新 |
| news | 4 | 综合新闻和热门话题 |
| dev | 6 | 开发、编程相关 |
| social | 4 | 社交媒体热门话题 |
| finance | 3 | 财经新闻 |
| entertainment | 2 | 娱乐和生活 |
| science | 2 | 科学和研究 |

### 源列表示例

#### 科技类
- 36氪快讯
- 少数派 Matrix
- GitHub 热门（日报）
- V2EX 热门话题
- Indie Hackers
- Hacker News

#### 新闻类
- 知乎热榜
- 微博热搜
- 百度热搜
- 今日头条新闻

#### 开发类
- Product Hunt
- GitHub 热门开发者
- 掘金热门（前端）
- 掘金热门（后端）
- CSDN 博客
- 阮一峰的网络日志

## 当前源管理（RSSSourcesManager）

### 存储位置

```bash
~/.her/rss_sources.json
```

### 默认源

默认启用 4 个科技类源：
```python
- /36kr/newsflash     # 36氪快讯
- /sspai/matrix       # 少数派 Matrix
- /github/trending/daily  # GitHub 热门
- /v2ex/topics/hot    # V2EX 热门
```

### 持久化格式

```json
{
  "version": "1.0",
  "sources": [
    {
      "id": "36kr_newsflash",
      "route": "/36kr/newsflash",
      "name": "36氪快讯",
      "description": "36氪科技快讯",
      "language": "zh-CN",
      "category": "tech"
    }
  ]
}
```

## 用户交互

### 添加 RSS 源

**中文命令**：
```
添加 RSS 源 知乎热榜
添加 RSS 源 zhihu_hot
```

**英文命令**：
```
add RSS source zhihu_hot
add RSS source "Hacker News"
```

**Her 的响应**：
- 成功：显示"已添加: [源名称]"
- 失败：显示"源已存在: [源ID]" 或显示可用源列表

### 删除 RSS 源

**中文命令**：
```
删除 RSS 源 知乎热榜
删除 RSS 源 zhihu_hot
```

**英文命令**：
```
remove RSS source zhihu_hot
remove RSS source "Hacker News"
```

**Her 的响应**：
- 成功：显示"已移除: [源名称]"
- 失败：显示"未找到源: [源ID]" 或显示当前源列表

### 查看 RSS 源

**中文命令**：
```
查看 RSS 源
列出 RSS 源
都有什么源
```

**英文命令**：
```
list RSS sources
show RSS sources
```

**Her 的响应**：
- 显示当前所有启用的源
- 包含 ID、名称、描述、类别、语言

### 查看所有可用源

如果用户尝试添加不存在的源，Her 会显示所有可用源：

```
可用的 RSS 源:

【TECH】
  [36kr_newsflash] 36氪快讯
    36氪科技快讯

【NEWS】
  [zhihu_hot] 知乎热榜
    知乎今日热榜

...

使用方式：添加 RSS 源 [ID] 或 添加 RSS 源 [名称]
```

## 意图识别

### 新增意图类型

```python
IntentType.ADD_RSS_SOURCE      # 添加 RSS 源
IntentType.REMOVE_RSS_SOURCE   # 删除 RSS 源
IntentType.LIST_RSS_SOURCES    # 列出 RSS 源
```

### 关键词模式

```python
ADD_RSS_SOURCE: [
    r"^添加.*(rss|源|订阅)",
    r"^(add|subscribe).*(rss|source|feed)",
    r"增加.*(rss|源)",
]
REMOVE_RSS_SOURCE: [
    r"^删除.*(rss|源|订阅)",
    r"^(remove|delete).*(rss|source|feed)",
    r"移除.*(rss|源)",
]
LIST_RSS_SOURCES: [
    r"^(显示|列出|查看).*?(rss|源|订阅)",
    r"^(list|show).*(rss|source|feed)",
    r"都有.*?源|看看.*?源",
]
```

## Agent 集成

### 初始化

```python
# Create sources manager
sources_manager = RSSSourcesManager()

# Get current routes
routes = sources_manager.get_current_routes()

# Create RSSHub with current routes
rsshub = create_rsshub(routes=routes)

# Create agent
agent = Her(
    llm=llm,
    rsshub=rsshub,
    sources_manager=sources_manager,  # Pass manager to agent
)
```

### 添加源流程

```
1. 用户输入："添加 RSS 源 知乎热榜"
2. 意图识别：ADD_RSS_SOURCE
3. Agent._handle_add_rss() 被调用
4. 搜索源（按 ID 或名称）
5. 从全集获取源信息
6. 调用 manager.add_source()
7. 更新 RSSHub 路由
8. 返回成功消息
```

### 删除源流程

```
1. 用户输入："删除 RSS 源 知乎热榜"
2. 意图识别：REMOVE_RSS_SOURCE
3. Agent._handle_remove_rss() 被调用
4. 从当前列表查找源
5. 调用 manager.remove_source()
6. 更新 RSSHub 路由
7. 返回成功消息
```

## API 参考

### RSSSourcesManager

```python
manager = RSSSourcesManager(file_path=None)

# Get current routes
routes = manager.get_current_routes()

# Add source
success, message = manager.add_source(
    source_id="zhihu_hot",
    route="/zhihu/hot",
    name="知乎热榜",
    description="知乎今日热榜",
    language="zh-CN",
    category="news",
)

# Remove source
success, message = manager.remove_source("zhihu_hot")

# List sources
text = manager.list_sources(category="tech")

# Get all sources
sources = manager.get_all_sources()
```

### RSS Sources All

```python
from her.infra.rss_sources_all import (
    RSS_SOURCES_ALL,
    get_source_by_id,
    get_source_by_route,
    get_sources_by_category,
    get_all_routes,
    format_sources_list,
)

# Get all sources
all_sources = RSS_SOURCES_ALL

# Find by ID
source = get_source_by_id("zhihu_hot")

# Find by route
source = get_source_by_route("/zhihu/hot")

# Get by category
tech_sources = get_sources_by_category("tech")

# Get all routes
all_routes = get_all_routes()

# Format for display
text = format_sources_list(tech_sources)
```

## 配置建议

### 添加更多类别

在 `rss_sources_all.py` 中添加：

```python
RSS_SOURCES_ALL = {
    # ... existing categories ...
    "sports": [
        {
            "id": "sports_news",
            "route": "/sports/news",
            "name": "体育新闻",
            "description": "体育综合新闻",
            "language": "zh-CN",
            "category": "sports",
        },
    ],
}
```

### 自定义存储位置

```python
from pathlib import Path

custom_path = Path.home() / "custom_location" / "my_rss_sources.json"
manager = RSSSourcesManager(file_path=custom_path)
```

## 测试

运行测试：
```bash
uv run python -c "
from her.infra.rss_sources_manager import RSSSourcesManager
from her.infra.rss_sources_all import RSS_SOURCES_ALL

manager = RSSSourcesManager()
print(f'Current sources: {len(manager.get_current_routes())}')
print(f'All available: {sum(len(s) for s in RSS_SOURCES_ALL.values())}')
"
```

## 未来改进

1. **源评分系统**
   - 记录每个源的使用频率
   - 基于用户兴趣自动推荐

2. **智能分类**
   - 基于内容自动分类
   - 支持多级分类体系

3. **源验证**
   - 测试源是否可用
   - 失败时自动降级

4. **批量管理**
   - 支持导入/导出配置
   - 支持预设配置文件

5. **订阅源**
   - 支持自定义 RSS URL
   - 支持用户自建 RSS 源
