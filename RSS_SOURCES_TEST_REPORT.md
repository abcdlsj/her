# RSS 源测试报告

## 测试日期
2026-01-03

## 测试方法
- 逐个测试所有 RSS 源的 HTTP 可用性
- 使用 `https://rsshub.rssforever.com` 作为基础 URL
- 请求超时：30 秒
- 请求间隔：0.5 秒（避免限流）

## 测试结果

### 总体统计
- **总测试源数**: 27
- **成功**: 7 (25.9%)
- **失败**: 20 (74.1%)

### 按类别统计

| 类别 | 总计 | 成功 | 失败 | 成功率 |
|------|------|------|------|--------|
| TECH | 6 | 3 | 3 | 50.0% |
| NEWS | 4 | 1 | 3 | 25.0% |
| DEV | 6 | 0 | 6 | 0.0% |
| SOCIAL | 4 | 1 | 3 | 25.0% |
| FINANCE | 3 | 1 | 2 | 33.3% |
| ENTERTAINMENT | 2 | 0 | 2 | 0.0% |
| SCIENCE | 2 | 1 | 1 | 50.0% |

### 成功的源（7 个）

#### 1. 技术类 (3 个)
- ✅ **少数派 Matrix** (`/sspai/matrix`)
  - 延迟: ~1000ms
  - 条目数: ~20

- ✅ **V2EX 热门话题** (`/v2ex/topics/hot`)
  - 延迟: ~800ms
  - 条目数: ~40

- ✅ **Hacker News** (`/hackernews/best`)
  - 延迟: ~1200ms
  - 条目数: ~30

#### 2. 新闻类 (1 个)
- ✅ **百度热搜** (`/baidu/search/hot`)
  - 延迟: ~900ms
  - 条目数: ~10

#### 3. 社交类 (1 个)
- ✅ **B站全站日榜** (`/bilibili/ranking/0/3`)
  - 延迟: ~1500ms
  - 条目数: ~100

#### 4. 财经类 (1 个)
- ✅ **华尔街见闻** (`/wallstreetcn/news`)
  - 延迟: ~1100ms
  - 条目数: ~25

#### 5. 科学类 (1 个)
- ✅ **Nature 研究** (`/nature/research`)
  - 延迟: ~1800ms
  - 条目数: ~15

### 失败的源（20 个）

所有失败源都返回 **HTTP 503** 错误（服务不可用）。

#### 技术类 (3 个)
- ❌ **36氪快讯** (`/36kr/newsflash`)
- ❌ **GitHub 热门（日报）** (`/github/trending/daily`)
- ❌ **Indie Hackers** (`/indiehackers/newest`)

#### 新闻类 (3 个)
- ❌ **知乎热榜** (`/zhihu/hot`)
- ❌ **微博热搜** (`/weibo/search/hot`)
- ❌ **今日头条新闻** (`/toutiao/news`)

#### 开发类 (6 个)
- ❌ **Product Hunt** (`/producthunt/today`)
- ❌ **GitHub 热门开发者** (`/github/trending/developers`)
- ❌ **掘金热门（前端）** (`/juejin/trending/frontend/daily`)
- ❌ **掘金热门（后端）** (`/juejin/trending/backend/daily`)
- ❌ **CSDN 博客** (`/csdn/blog`)
- ❌ **阮一峰的网络日志** (`/ruanyifeng/blog`)

#### 社交类 (3 个)
- ❌ **B站科技日榜** (`/bilibili/ranking/168/3`)
- ❌ **Twitter 热门** (`/twitter/trending`)
- ❌ **Reddit 热门** (`/reddit/hot`)

#### 财经类 (2 个)
- ❌ **东方财富新闻** (`/eastmoney/news`)
- ❌ **36氪财经** (`/36kr/finance`)

#### 娱乐类 (2 个)
- ❌ **豆瓣新片预告** (`/douban/movie/coming_soon`)
- ❌ **豆瓣电影口碑榜** (`/douban/movie/weekly_chart`)

#### 科学类 (1 个)
- ❌ **arXiv AI 论文** (`/arxiv/ai`)

## 默认配置

基于测试结果，默认启用以下 4 个核心源：

1. 少数派 Matrix - 科技优质内容
2. V2EX 热门话题 - 开发者社区
3. 百度热搜 - 热点话题
4. B站全站日榜 - 娱乐内容

这些源覆盖了多个类别，且都经过了验证可用。

## 建议

1. **定期重新测试**：每周运行一次测试脚本，检测源是否恢复可用
2. **添加备用源**：为每个类别准备备用源，主源不可用时自动切换
3. **监控 RSSHub 实例**：503 错误可能是临时性的，可以尝试其他 RSSHub 实例
4. **源优先级**：根据用户兴趣和反馈，为不同源设置优先级

## 重新测试失败的源

如果某些源恢复可用，可以通过以下方式重新测试：

```bash
# 测试单个源
curl -I https://rsshub.rssforever.com/zhihu/hot

# 或者运行完整测试
uv run python test_rss_sources.py
```

## 更新源列表

如果需要添加新源或修改现有源：

1. 在 `her/infra/rss_sources_all.py` 中添加源定义
2. 使用 `uv run python test_rss_sources.py` 验证可用性
3. 通过 Her 的添加源功能添加：`添加 RSS 源 [源ID]`

## 测试脚本

测试脚本位于 `test_rss_sources.py`，可用于：
- 测试所有源
- 生成详细报告
- 按类别汇总结果
- 列出失败的源路由

```bash
uv run python test_rss_sources.py
```
