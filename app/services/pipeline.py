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
from app.services.collector.search import NewsCollector, NewsItem
from app.services.guard.blocklist import is_topic_risky
from app.services.guard.service import GuardService
from app.services.humanizer.service import HumanizerService
from app.services.selector.service import TopicSelectorService
from app.services.wechat.cover_generator import generate_cover_async
from app.services.wechat.reading_guide import build_reading_guide_html
from app.services.wechat.service import WechatPublishOrchestrator
from app.services.writer.service import WriterService

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
    def __init__(self) -> None:
        self.settings = get_settings()
        self.writer = WriterService(author=self.settings.content_author)
        self.humanizer = HumanizerService()
        self.guard = GuardService()
        self.wechat = WechatPublishOrchestrator()
        self.news = NewsCollector()
        self.selector = TopicSelectorService()

    def _build_reading_guide_html(self, exclude_article_id: int | None = None) -> str:
        """构造底部「精彩文章导读」HTML（随机取3篇已发表文章）。"""
        with get_db_session() as session:
            guide_articles = get_random_published_articles(
                session, count=3, exclude_article_id=exclude_article_id
            )
        return build_reading_guide_html(guide_articles)

    async def generate_preview(self, request: ArticlePreviewRequest) -> ArticlePreviewResponse:
        """预览：对指定话题搜索素材并生成文章。"""
        context = await self.news.fetch_topic_detail(request.topic)
        context_text = context.to_prompt_text()

        draft = await self.writer.generate(
            topic=request.topic,
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
        """执行完整批次：获取新闻池 → LLM 选题 → 搜索详情 → 生成 → 改写 → 审核 → 发布。"""
        # 1. 获取今日新闻池
        news_items = await self.news.fetch_news_pool()
        if not news_items:
            logger.warning("未获取到任何新闻，批次 %s 跳过", batch_type)
            return []

        # 1.5 去重：过滤掉近3天已选过的话题（语义相似度匹配）
        with get_db_session() as session:
            already = get_recent_selected_topics(session, days=3)
            used_titles = {t.title for t in already}
        if used_titles:
            before = len(news_items)
            news_items = [n for n in news_items if not _is_similar_to_any(n.title, used_titles)]
            logger.info("去重过滤: %d → %d 条 (已选 %d 个话题，跨3天)", before, len(news_items), len(used_titles))

        if not news_items:
            logger.warning("去重后无可用新闻，批次 %s 跳过", batch_type)
            return []

        logger.info("新闻池获取 %d 条，开始 LLM 选题", len(news_items))

        # 2. LLM 选题
        selection = await self.selector.select(news_items, short_count=count, long_count=0, category=category)

        results = []
        all_selected = selection.get("short", []) + selection.get("long", [])

        if not all_selected:
            logger.warning("LLM 未选出任何话题，批次 %s 跳过", batch_type)
            return []

        for news_item in all_selected:
            try:
                result = await self._process_single_article(news_item)
                results.append(result)
            except Exception as exc:
                logger.error("文章处理失败 [%s]: %s", news_item.title, exc)
                results.append({
                    "title": news_item.title, "status": "failed", "error": str(exc),
                })

        logger.info("批次 %s 完成: %d 篇文章", batch_type, len(results))
        return results

    async def _process_single_article(self, news_item: NewsItem) -> dict:
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
            topic_title, context_text=context_text,
        )
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

        # 改写重试：评分不达标则重新调用 humanizer（最多3次）
        retry_count = 0
        while humanized["style_score"] < 80 and retry_count < 3:
            retry_count += 1
            logger.warning(
                "改写评分 %d < 80，第 %d 次重试: %s",
                humanized["style_score"], retry_count, draft["title"],
            )
            humanized = await self.humanizer.rewrite(draft)
            with get_db_session() as session:
                update_article_status(
                    session, article_id, "humanized",
                    content_md=humanized["content_markdown"],
                    content_html=humanized["content_html"],
                    style_score=humanized["style_score"],
                )

        if humanized["style_score"] < 80:
            logger.warning("改写 %d 次后评分仍 %d < 80，跳过发布: %s", retry_count, humanized["style_score"], draft["title"])
            return {"title": draft["title"], "status": "low_quality", "article_id": article_id}

        # 底部导读区块：随机取3篇已发表文章追加到正文末尾
        guide_html = self._build_reading_guide_html(exclude_article_id=article_id)
        if guide_html:
            humanized["content_html"] = humanized["content_html"] + guide_html

        # 发布
        cover_path = await generate_cover_async(
            humanized["title"],
            content=humanized["content_html"],
        )
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
                update_article_status(
                    session,
                    article_id,
                    final_status,
                    content_html=payload.content,
                )
                save_publish_record(
                    session,
                    article_id=article_id,
                    draft_media_id=result.draft_media_id,
                    publish_id=result.publish_id or "",
                    article_url=result.article_url or "",
                    publish_status=result.publish_status,
                    raw_response=result.model_dump(),
                    cover_media_id=result.cover_media_id,
                )
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
