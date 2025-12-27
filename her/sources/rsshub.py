"""RSSHub source - access various platforms via RSSHub."""

from her.sources.rss import RSSSource

# 官方实例（也可自建）
DEFAULT_RSSHUB_INSTANCE = "https://rsshub.rssforever.com"


class RSSHubSource(RSSSource):
    """
    通过 RSSHub 获取各平台信息。

    RSSHub 可以将微博、B站、知乎、Twitter 等转换为 RSS 格式。
    文档: https://docs.rsshub.app

    使用示例:
        # 使用官方实例
        source = RSSHubSource("科技资讯", [
            "/36kr/newsflash",           # 36氪快讯
            "/sspai/matrix",             # 少数派 Matrix
            "/zhihu/hot",                # 知乎热榜
        ])

        # 使用自建实例
        source = RSSHubSource(
            "我的订阅",
            ["/bilibili/ranking/0/3"],
            instance="https://my-rsshub.example.com"
        )

    常用路由:
        # 科技
        /36kr/newsflash              - 36氪快讯
        /sspai/matrix                - 少数派 Matrix
        /ithome/ranking/daily        - IT之家日榜
        /huxiu/article               - 虎嗅文章

        # 社交
        /weibo/search/hot            - 微博热搜
        /zhihu/hot                   - 知乎热榜
        /douban/movie/playing        - 豆瓣正在热映

        # 视频
        /bilibili/ranking/0/3        - B站全站日榜
        /youtube/channel/:id         - YouTube 频道

        # 开发者
        /github/trending/daily       - GitHub Trending
        /producthunt/today           - Product Hunt 今日
        /v2ex/topics/hot             - V2EX 热门

        # 新闻
        /economist/latest            - 经济学人
        /wsj/en-us/world             - 华尔街日报
    """

    def __init__(
        self,
        name: str,
        routes: list[str],
        instance: str = DEFAULT_RSSHUB_INSTANCE,
    ):
        feed_urls = [f"{instance.rstrip('/')}{route}" for route in routes]
        super().__init__(name, feed_urls)
        self.instance = instance
        self.routes = routes
