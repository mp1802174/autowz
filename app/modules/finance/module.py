"""财经内容模块

实现财经数据解读型内容的完整生产链路。
"""

import logging
from datetime import date
from typing import List

from app.db.crud import (
    get_recent_selected_topics,
    save_article,
    save_publish_record,
    save_topic,
    update_article_status,
)
from app.db.engine import get_db_session
from app.modules.base import BaseContentModule
from app.modules.finance.config import (
    AUTHOR,
    DISPLAY_NAME,
    MODULE_NAME,
    SCHEDULE_SLOTS,
    SELECTOR_CONFIG,
    WRITER_CONFIG,
)
from app.modules.finance.writer import DataDrivenWriter
from app.services.collector.search import NewsCollector, NewsItem
from app.services.guard.blocklist import is_topic_risky
from app.services.guard.service import GuardService
from app.services.selector.service import TopicSelectorService
from app.services.publish import (
    ArticleProduct,
    BaijiahaoChannel,
    PublishRouter,
    ToutiaoChannel,
    WechatChannel,
)
from app.services.wechat.cover_generator import generate_cover_async
from app.core.config import get_settings

logger = logging.getLogger("autowz.finance.module")


def _normalize_title(title: str) -> str:
    """标题归一化,用于去重"""
    import re
    return re.sub(r'[^一-鿿\w]', '', title).lower()


def _is_similar_to_any(title: str, candidates: set[str], threshold: float = 0.50) -> bool:
    """检查标题是否与候选集相似"""
    nt = _normalize_title(title)
    if not nt:
        return False
    for c in candidates:
        nc = _normalize_title(c)
        if not nc:
            continue
        if nt == nc:
            return True
        if len(nt) >= 4 and len(nc) >= 4 and (nt in nc or nc in nt):
            return True
        from difflib import SequenceMatcher
        if SequenceMatcher(None, nt, nc).ratio() >= threshold:
            return True
    return False


class FinanceModule(BaseContentModule):
    """财经内容模块

    特点:
    - 数据驱动解读型写作
    - 聚焦财经/宏观/产业话题
    - 每天1篇精品
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.collector = NewsCollector()
        self.selector = TopicSelectorService(
            priority_keywords=SELECTOR_CONFIG.get("priority_keywords"),
            downrank_keywords=SELECTOR_CONFIG.get("downrank_keywords"),
            blacklist_keywords=SELECTOR_CONFIG.get("blacklist_keywords"),
        )
        self.writer = DataDrivenWriter(author=AUTHOR, **WRITER_CONFIG)
        self.guard = GuardService()
        self.router = self._build_router()

    def _build_router(self) -> PublishRouter:
        all_channels = [WechatChannel(), ToutiaoChannel(), BaijiahaoChannel()]
        channels = [ch for ch in all_channels if ch.name in self._publish_targets]
        return PublishRouter(channels, min_quality=0.0)

    @property
    def _publish_targets(self) -> List[str]:
        raw = self.settings.publish_targets or "wechat"
        return [t.strip() for t in raw.split(",") if t.strip()]

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
        """采集财经新闻池"""
        return await self.collector.fetch_news_pool()

    async def select_topics(self, pool: List[NewsItem], count: int) -> List[NewsItem]:
        """选出最适合财经解读的话题"""
        # 使用财经优先的选题策略
        selection = await self.selector.select(
            pool,
            short_count=count,
            long_count=0,
            category="finance"
        )
        return selection.get("short", []) + selection.get("long", [])

    async def generate_article(self, topic: NewsItem) -> dict:
        """生成数据解读型财经文章"""
        # 搜索详细报道作为素材
        context = await self.collector.fetch_topic_detail(topic.title)
        context_text = context.to_prompt_text()

        # 如果搜索没有结果,用新闻本身的描述作为素材
        if not context_text and topic.description:
            context_text = (
                f"以下是该新闻的基本信息(请基于此撰写,不要编造细节):\n\n"
                f"1. {topic.title}(来源:{topic.source})\n"
                f"   {topic.description}\n"
            )

        # Phase 1: 单次生成,不再调用 humanizer
        article = await self.writer.generate(
            topic.title,
            context_text=context_text,
        )

        return article

    async def run_batch(self, count: int = 1) -> List[dict]:
        """执行完整批次"""
        # 1. 采集新闻池
        news_items = await self.collect_topics()
        if not news_items:
            logger.warning("未获取到任何新闻,批次跳过")
            return []

        # 1.5 去重:过滤近3天已选过的话题
        with get_db_session() as session:
            already = get_recent_selected_topics(session, days=3)
            used_titles = {t.title for t in already}

        if used_titles:
            before = len(news_items)
            news_items = [n for n in news_items if not _is_similar_to_any(n.title, used_titles)]
            logger.info("去重过滤: %d → %d 条(已选%d个话题,跨3天)", before, len(news_items), len(used_titles))

        if not news_items:
            logger.warning("去重后无可用新闻,批次跳过")
            return []

        logger.info("新闻池获取%d条,开始选题", len(news_items))

        # 2. 选题
        selected = await self.select_topics(news_items, count)
        if not selected:
            logger.warning("未选出任何话题,批次跳过")
            return []

        # 3. 逐篇生成并发布
        results = []
        for news_item in selected:
            try:
                result = await self._process_single_article(news_item)
                results.append(result)
            except Exception as exc:
                logger.error("文章处理失败[%s]: %s", news_item.title, exc, exc_info=True)
                results.append({
                    "title": news_item.title,
                    "status": "failed",
                    "error": str(exc),
                })

        logger.info("批次完成: %d篇文章", len(results))
        return results

    async def _process_single_article(self, news_item: NewsItem) -> dict:
        """处理单篇文章的完整流程"""
        topic_title = news_item.title

        # 存话题
        with get_db_session() as session:
            db_topic = save_topic(
                session,
                title=topic_title,
                source=news_item.source,
                hot_score=0,
                summary=news_item.description,
                source_url=news_item.url,
                batch_date=date.today(),
                status="selected",
            )
            topic_id = db_topic.id

        # 生成文章
        draft = await self.generate_article(news_item)

        # 存文章
        with get_db_session() as session:
            db_article = save_article(
                session,
                topic_id=topic_id,
                article_type="comment",
                title=draft["title"],
                digest=draft["digest"],
                content_md=draft["content_markdown"],
                content_html=draft["content_html"],
                style_score=draft["style_score"],
                status="drafted",
            )
            article_id = db_article.id

        # Phase 1: 不再调用 humanizer,直接标记为 humanized
        with get_db_session() as session:
            update_article_status(
                session, article_id, "humanized",
                content_md=draft["content_markdown"],
                content_html=draft["content_html"],
                style_score=draft["style_score"],
            )

        # 审核
        review = await self.guard.review(draft)
        risk_level = review["risk_level"]
        with get_db_session() as session:
            update_article_status(session, article_id, "reviewed", risk_level=risk_level)

        if risk_level == "high":
            with get_db_session() as session:
                update_article_status(session, article_id, "failed")
            return {"title": draft["title"], "status": "blocked_high_risk", "article_id": article_id}

        # 生成封面
        cover_path = await generate_cover_async(
            draft["title"],
            content=draft["content_html"],
        )

        # 发布
        product = ArticleProduct(
            title=draft["title"],
            digest=draft["digest"],
            content_html=draft["content_html"],
            content_md=draft["content_markdown"],
            author=self.author,
            cover_path=cover_path,
            quality_score=draft["style_score"],
            article_id=article_id,
            ai_disclosure=True,
        )

        with get_db_session() as session:
            update_article_status(session, article_id, "publishing")

        try:
            results = await self.router.publish(product, targets=self._publish_targets, as_draft=True)

            any_ok = any(r.ok for r in results.values())
            final_status = "draft_saved" if any_ok else "failed"

            with get_db_session() as session:
                update_article_status(
                    session, article_id, final_status,
                    content_html=draft["content_html"],
                )
                for ch_name, r in results.items():
                    save_publish_record(
                        session,
                        article_id=article_id,
                        draft_media_id=r.draft_id or "",
                        publish_id="",
                        article_url=r.url or "",
                        publish_status=r.status,
                        raw_response=r.raw if isinstance(r.raw, dict) else {},
                        cover_media_id="",
                    )

            return {
                "title": draft["title"],
                "status": final_status,
                "article_id": article_id,
                "publish_results": {k: {"ok": v.ok, "status": v.status, "draft_id": v.draft_id, "error": v.error} for k, v in results.items()},
            }
        except Exception:
            with get_db_session() as session:
                update_article_status(session, article_id, "failed")
            raise
