"""内容模块基类

所有内容生产模块的抽象基类,定义统一接口。
每个模块(财经/娱乐/视频等)都实现这套接口,但具体实现完全独立。
"""

from abc import ABC, abstractmethod
from typing import List

from app.services.collector.search import NewsItem


class BaseContentModule(ABC):
    """内容模块基类

    每个内容模块负责完整的"采集→选题→生成→审核→发布"链路,
    但可以有完全不同的实现(数据源、写作风格、频率等)。

    公共基础设施(LLM/发布/审核/数据库)由子类通过依赖注入使用。
    """

    @property
    @abstractmethod
    def module_name(self) -> str:
        """模块唯一标识(如 'finance', 'entertainment')"""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """模块显示名称(如 '财经观察', '娱乐吃瓜')"""
        pass

    @property
    @abstractmethod
    def author(self) -> str:
        """作者署名(如 '现象观察', '吃瓜群众')"""
        pass

    @abstractmethod
    async def collect_topics(self) -> List[NewsItem]:
        """采集选题池

        不同模块可以用完全不同的数据源:
        - 财经: 天行API + RSS + 搜狗新闻
        - 娱乐: 微博热搜 + 抖音热榜
        - 视频: YouTube 热门 + B站排行
        """
        pass

    @abstractmethod
    async def select_topics(self, pool: List[NewsItem], count: int) -> List[NewsItem]:
        """从选题池中选出值得写的话题

        不同模块有不同的选题标准:
        - 财经: 优先宏观数据/行业景气/政策影响
        - 娱乐: 优先话题性/争议度/流量
        """
        pass

    @abstractmethod
    async def generate_article(self, topic: NewsItem) -> dict:
        """生成文章

        返回包含以下字段的 dict:
        - title: 标题
        - digest: 摘要
        - content_markdown: Markdown 正文
        - content_html: HTML 正文
        - style_score: 风格评分

        不同模块有完全不同的写作结构和风格:
        - 财经: 钩子→数据→解读→影响→判断
        - 娱乐: 反转→爆料→情绪→共鸣
        """
        pass

    async def run_batch(self, count: int = 1) -> List[dict]:
        """执行完整批次(采集→选题→生成→审核→发布)

        这是所有模块共享的流程框架,但每一步的具体实现由子类控制。
        公共的审核/封面/发布逻辑在这里统一处理。
        """
        # 子类可以覆盖此方法实现完全自定义的流程
        raise NotImplementedError("子类应实现 run_batch 或使用 ArticlePipeline")
