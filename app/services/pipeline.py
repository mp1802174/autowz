import logging
from datetime import date

from app.core.config import get_settings
from app.db.crud import get_selected_topics, save_article, save_topic, update_article_status
from app.db.engine import get_db_session
from app.models.schemas import (
    ArticlePreviewRequest,
    ArticlePreviewResponse,
    PublishArticleRequest,
    PublishArticleResponse,
    WechatArticlePayload,
)
from app.services.collector.search import NewsCollector, NewsItem
from app.services.guard.service import GuardService
from app.services.humanizer.service import HumanizerService
from app.services.selector.service import TopicSelectorService
from app.services.wechat.cover_generator import generate_cover
from app.services.wechat.service import WechatPublishOrchestrator
from app.services.writer.service import WriterService

logger = logging.getLogger("autowz.pipeline")


class ArticlePipeline:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.writer = WriterService(author=self.settings.content_author)
        self.humanizer = HumanizerService()
        self.guard = GuardService()
        self.wechat = WechatPublishOrchestrator()
        self.news = NewsCollector()
        self.selector = TopicSelectorService()

    async def generate_preview(self, request: ArticlePreviewRequest) -> ArticlePreviewResponse:
        """预览：对指定话题搜索素材并生成文章。"""
        context = await self.news.fetch_topic_detail(request.topic)
        context_text = context.to_prompt_text()

        draft = await self.writer.generate(
            topic=request.topic,
            article_type=request.article_type,
            stance=request.stance,
            context_text=context_text,
        )
        humanized = await self.humanizer.rewrite(draft)
        review = await self.guard.review(humanized)

        return ArticlePreviewResponse(
            title=humanized["title"],
            digest=humanized["digest"],
            content_markdown=humanized["content_markdown"],
            content_html=humanized["content_html"],
            risk_level=review["risk_level"],
            style_score=humanized["style_score"],
        )

    async def publish(self, request: PublishArticleRequest) -> PublishArticleResponse:
        preview = await self.generate_preview(
            ArticlePreviewRequest(
                topic=request.topic,
                article_type=request.article_type,
                stance=request.stance,
            )
        )
        if preview.risk_level == "high":
            raise ValueError("内容风险等级过高，已阻止自动发布。")

        if preview.style_score < 80:
            logger.warning("文章质量评分 %d < 80，跳过发布", preview.style_score)
            raise ValueError(f"文章质量评分不足 ({preview.style_score}/100)，请人工审核。")

        cover_path = request.cover_image_path or generate_cover(preview.title)

        payload = WechatArticlePayload(
            title=preview.title,
            author=self.settings.content_author,
            digest=preview.digest,
            content=preview.content_html,
            content_source_url=str(request.source_url or ""),
            thumb_media_id="TO_BE_FILLED",
            need_open_comment=self.settings.default_comment_open,
            only_fans_can_comment=self.settings.default_fans_comment_only,
        )

        result = await self.wechat.publish_article(payload, cover_path)
        return PublishArticleResponse(title=preview.title, **result.model_dump())

    async def collect_topics(self) -> list[dict]:
        """采集今日新闻池并存入数据库。"""
        news_items = await self.news.fetch_news_pool()
        saved = []
        with get_db_session() as session:
            for item in news_items:
                db_topic = save_topic(
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
        logger.info("新闻池采集完成，存入 %d 条", len(saved))
        return saved

    async def run_batch(self, batch_type: str = "morning") -> list[dict]:
        """执行完整批次：获取新闻池 → LLM 选题 → 搜索详情 → 生成 → 改写 → 审核 → 发布。"""
        # 1. 获取今日新闻池
        news_items = await self.news.fetch_news_pool()
        if not news_items:
            logger.warning("未获取到任何新闻，批次 %s 跳过", batch_type)
            return []

        # 1.5 去重：过滤掉当天已选过的话题
        with get_db_session() as session:
            already = get_selected_topics(session, date.today())
            used_titles = {t.title for t in already}
        if used_titles:
            before = len(news_items)
            news_items = [n for n in news_items if n.title not in used_titles]
            logger.info("去重过滤: %d → %d 条 (已选 %d 个话题)", before, len(news_items), len(used_titles))

        if not news_items:
            logger.warning("去重后无可用新闻，批次 %s 跳过", batch_type)
            return []

        logger.info("新闻池获取 %d 条，开始 LLM 选题", len(news_items))

        # 2. LLM 选题
        if batch_type == "evening":
            selection = await self.selector.select(news_items, short_count=0, long_count=1)
        else:
            selection = await self.selector.select(news_items, short_count=1, long_count=0)

        results = []
        all_selected = selection.get("short", []) + selection.get("long", [])

        if not all_selected:
            logger.warning("LLM 未选出任何话题，批次 %s 跳过", batch_type)
            return []

        for news_item in all_selected:
            article_type = "long" if news_item in selection.get("long", []) else "short"
            try:
                result = await self._process_single_article(news_item, article_type)
                results.append(result)
            except Exception as exc:
                logger.error("文章处理失败 [%s]: %s", news_item.title, exc)
                results.append({
                    "title": news_item.title, "status": "failed", "error": str(exc),
                })

        logger.info("批次 %s 完成: %d 篇文章", batch_type, len(results))
        return results

    async def _process_single_article(self, news_item: NewsItem, article_type: str) -> dict:
        """处理单篇文章的完整流程。"""
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

        # 搜索详细报道作为写作素材
        context = await self.news.fetch_topic_detail(topic_title)
        context_text = context.to_prompt_text()

        # 如果搜索没有结果，用新闻本身的描述作为素材
        if not context_text and news_item.description:
            context_text = (
                f"以下是该新闻的基本信息（请基于此撰写，不要编造细节）：\n\n"
                f"1. {news_item.title}（来源：{news_item.source}）\n"
                f"   {news_item.description}\n"
            )

        # 生成
        draft = await self.writer.generate(
            topic_title, article_type, context_text=context_text,
        )
        with get_db_session() as session:
            db_article = save_article(
                session,
                topic_id=topic_id,
                article_type=article_type,
                title=draft["title"],
                digest=draft["digest"],
                content_md=draft["content_markdown"],
                content_html=draft["content_html"],
                style_score=draft["style_score"],
                status="drafted",
            )
            article_id = db_article.id

        # 改写
        humanized = await self.humanizer.rewrite(draft)
        with get_db_session() as session:
            update_article_status(
                session, article_id, "humanized",
                content_md=humanized["content_markdown"],
                content_html=humanized["content_html"],
                style_score=humanized["style_score"],
            )

        # 审核
        review = await self.guard.review(humanized)
        risk_level = review["risk_level"]
        with get_db_session() as session:
            update_article_status(session, article_id, "reviewed", risk_level=risk_level)

        if risk_level == "high":
            with get_db_session() as session:
                update_article_status(session, article_id, "failed")
            return {"title": draft["title"], "status": "blocked_high_risk", "article_id": article_id}

        if humanized["style_score"] < 80:
            logger.warning("评分 %d < 80，跳过发布: %s", humanized["style_score"], draft["title"])
            return {"title": draft["title"], "status": "low_quality", "article_id": article_id}

        # 发布
        cover_path = generate_cover(humanized["title"])
        payload = WechatArticlePayload(
            title=humanized["title"],
            author=self.settings.content_author,
            digest=humanized["digest"],
            content=humanized["content_html"],
            thumb_media_id="TO_BE_FILLED",
            need_open_comment=self.settings.default_comment_open,
            only_fans_can_comment=self.settings.default_fans_comment_only,
        )

        with get_db_session() as session:
            update_article_status(session, article_id, "publishing")

        try:
            result = await self.wechat.publish_article(payload, cover_path)
            final_status = "published" if result.publish_status == "success" else result.publish_status
            with get_db_session() as session:
                update_article_status(session, article_id, final_status)
            return {
                "title": humanized["title"],
                "status": final_status,
                "article_id": article_id,
                "publish_result": result.model_dump(),
            }
        except Exception:
            with get_db_session() as session:
                update_article_status(session, article_id, "failed")
            raise
