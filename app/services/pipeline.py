"""文章生产管道(向后兼容旧API)

Phase 1 重构说明:
- 底层改为模块化架构(app/modules/),支持多套独立内容配方
- 默认使用 FinanceModule(财经数据解读型)
- 保留旧 API 接口,内部委托给模块实现

未来扩展:
- 可新增 EntertainmentModule/VideoModule 等,切换 module_name 即可
"""

import logging
import re
from datetime import date

from app.core.config import get_settings
from app.db.crud import get_random_published_articles, get_recent_selected_topics, save_article, save_publish_record, save_topic, save_topic_upsert, update_article_status
from app.db.engine import get_db_session
from app.models.schemas import (
    ArticlePreviewRequest,
    ArticlePreviewResponse,
    PublishArticleRequest,
    PublishArticleResponse,
    WechatArticlePayload,
)
from app.modules.registry import get_module
from app.services.collector.search import NewsCollector, NewsItem
from app.services.guard.blocklist import is_topic_risky
from app.services.guard.service import GuardService
from app.services.wechat.cover_generator import generate_cover_async
from app.services.wechat.reading_guide import build_reading_guide_html
from app.services.wechat.service import WechatPublishOrchestrator

logger = logging.getLogger("autowz.pipeline")


def _normalize_title(title: str) -> str:
    """去除标点和空白，只保留中文字符和字母数字用于相似度比较。"""
    return re.sub(r'[^\u4e00-\u9fff\w]', '', title).lower()


def _is_similar_to_any(title: str, candidates: set[str], threshold: float = 0.50) -> bool:
    """检查 title 是否与 candidates 中任意一条语义相似（子串 / 编辑距离）。"""
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


class ArticlePipeline:
    """文章生产管道(向后兼容层)

    Phase 1 重构:底层委托给模块化架构,默认使用 FinanceModule。
    保留旧 API 接口,方便平滑迁移。
    """

    def __init__(self, module_name: str = "finance") -> None:
        self.settings = get_settings()
        self.module = get_module(module_name)

        # 向后兼容:暴露底层服务(某些路由可能直接访问)
        self.guard = GuardService()
        self.wechat = WechatPublishOrchestrator()
        self.news = NewsCollector()

    def _build_reading_guide_html(self, exclude_article_id: int | None = None) -> str:
        """构造底部「精彩文章导读」HTML（随机取3篇已发表文章）。"""
        with get_db_session() as session:
            guide_articles = get_random_published_articles(
                session, count=3, exclude_article_id=exclude_article_id
            )
        return build_reading_guide_html(guide_articles)

    async def generate_preview(self, request: ArticlePreviewRequest) -> ArticlePreviewResponse:
        """预览:对指定话题搜索素材并生成文章。

        Phase 1: 委托给模块实现,不再调用 humanizer。
        """
        # 构造临时 NewsItem
        news_item = NewsItem(
            title=request.topic,
            source="manual",
            description="",
        )

        # 委托给模块生成文章
        draft = await self.module.generate_article(news_item)

        # 审核
        review = await self.guard.review(draft)

        return ArticlePreviewResponse(
            title=draft["title"],
            digest=draft["digest"],
            content_markdown=draft["content_markdown"],
            content_html=draft["content_html"],
            risk_level=review["risk_level"],
            style_score=draft["style_score"],
        )

    async def publish(self, request: PublishArticleRequest) -> PublishArticleResponse:
        # 早期硬拦截：手动话题先过 blocklist，避免浪费 LLM 调用
        # 高/中风险均阻止生成，避免公众号侧限流
        risky, level, hit = is_topic_risky(request.topic or "")
        if risky:
            logger.warning("publish 拒绝 %s 风险话题 [%s]: %s", level, hit, request.topic)
            raise ValueError(f"话题命中{level}风险词 [{hit}]，已阻止生成与发布。")

        preview = await self.generate_preview(
            ArticlePreviewRequest(
                topic=request.topic,
                stance=request.stance,
            )
        )
        if preview.risk_level == "high":
            raise ValueError("内容风险等级过高，已阻止自动发布。")

        if preview.style_score < 80:
            logger.warning("文章质量评分 %d < 80，跳过发布", preview.style_score)
            raise ValueError(f"文章质量评分不足 ({preview.style_score}/100)，请人工审核。")

        # 底部导读区块：随机取3篇已发表文章追加到正文末尾
        content_html = preview.content_html
        guide_html = self._build_reading_guide_html()
        if guide_html:
            content_html = content_html + guide_html

        cover_path = request.cover_image_path or await generate_cover_async(
            preview.title,
            content=content_html,
        )

        payload = WechatArticlePayload(
            title=preview.title,
            author=self.settings.content_author,
            digest=preview.digest,
            content=content_html,
            content_source_url=str(request.source_url or ""),
            thumb_media_id="TO_BE_FILLED",
            need_open_comment=self.settings.default_comment_open,
            only_fans_can_comment=self.settings.default_fans_comment_only,
        )

        result = await self.wechat.publish_article(payload, cover_path)
        return PublishArticleResponse(title=preview.title, **result.model_dump())

    async def collect_topics(self) -> list[dict]:
        """采集今日新闻池并存入数据库（标题+日期去重）。"""
        news_items = await self.news.fetch_news_pool()
        saved = []
        with get_db_session() as session:
            for item in news_items:
                db_topic = save_topic_upsert(
                    session,
                    title=item.title,
                    source=item.source,
                    hot_score=0,
                    summary=item.description,
                    source_url=item.url,
                    batch_date=date.today(),
                )
                saved.append({
                    "id": db_topic.id, "title": db_topic.title, "source": db_topic.source,
                })
        logger.info("新闻池采集完成，存入 %d 条（去重后）", len(saved))
        return saved

    async def run_batch(self, batch_type: str = "morning", count: int = 1, category: str = None) -> list[dict]:
        """执行完整批次

        Phase 1: 委托给模块实现,简化为统一调用。
        """
        logger.info("批次 %s 开始,委托给模块 %s", batch_type, self.module.module_name)
        results = await self.module.run_batch(count)
        logger.info("批次 %s 完成: %d 篇文章", batch_type, len(results))
        return results

    async def _process_single_article(self, news_item: NewsItem) -> dict:
        """处理单篇文章(已废弃,委托给模块实现)"""
        logger.warning("_process_single_article 已废弃,请直接使用模块的 run_batch")
        return await self.module._process_single_article(news_item)
