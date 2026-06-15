"""娱乐内容模块。"""

from typing import List

from app.core.config import get_settings
from app.modules.entertainment.config import (
    AUTHOR,
    DISPLAY_NAME,
    MODULE_NAME,
    SCHEDULE_SLOTS,
    SELECTOR_CONFIG,
    WRITER_CONFIG,
)
from app.modules.entertainment.writer import EntertainmentWriter
from app.modules.finance.module import FinanceModule
from app.services.collector.search import NewsCollector, NewsItem
from app.services.guard.service import GuardService
from app.services.selector.service import TopicSelectorService
from app.services.wechat.service import WechatPublishOrchestrator


class EntertainmentModule(FinanceModule):
    """娱乐内容模块。

    先复用现有新闻采集/入库/审核/发布链路，只替换选题配置和写作人设。
    默认不会启用；只有 ACTIVE_MODULE=entertainment 或 ArticlePipeline("entertainment") 才使用。
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.collector = NewsCollector()
        self.selector = TopicSelectorService(
            priority_keywords=SELECTOR_CONFIG.get("priority_keywords"),
            downrank_keywords=SELECTOR_CONFIG.get("downrank_keywords"),
            blacklist_keywords=SELECTOR_CONFIG.get("blacklist_keywords"),
        )
        self.writer = EntertainmentWriter(author=AUTHOR, **WRITER_CONFIG)
        self.guard = GuardService()
        self.wechat = WechatPublishOrchestrator()

    @property
    def module_name(self) -> str:
        return MODULE_NAME

    @property
    def display_name(self) -> str:
        return DISPLAY_NAME

    @property
    def author(self) -> str:
        return AUTHOR

    @property
    def schedule_slots(self):
        return SCHEDULE_SLOTS

    async def collect_topics(self) -> List[NewsItem]:
        """第一版复用现有新闻池；后续可接娱乐热榜。"""
        return await self.collector.fetch_news_pool()

    async def select_topics(self, pool: List[NewsItem], count: int) -> List[NewsItem]:
        selection = await self.selector.select(
            pool,
            short_count=count,
            long_count=0,
            category="entertainment",
        )
        return selection.get("short", []) + selection.get("long", [])

    async def generate_article(self, topic: NewsItem) -> dict:
        context = await self.collector.fetch_topic_detail(topic.title)
        context_text = context.to_prompt_text()

        if not context_text and topic.description:
            context_text = (
                f"以下是该娱乐话题的基本信息(请基于此撰写,不要编造细节):\n\n"
                f"1. {topic.title}(来源:{topic.source})\n"
                f"   {topic.description}\n"
            )

        return await self.writer.generate(
            topic.title,
            context_text=context_text,
        )
