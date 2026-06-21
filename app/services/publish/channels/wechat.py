"""WechatChannel —— 把现有 app/services/wechat 发布编排包装成统一 Channel。

统一保存草稿；真实发布必须人工审核后手动操作。
本类做接口适配(ArticleProduct → WechatArticlePayload)，并只在微信正文追加导读区块。
"""
from __future__ import annotations

import logging
import re

from app.core.config import get_settings
from app.models.schemas import WechatArticlePayload
from app.services.publish.base import Channel
from app.services.publish.product import ArticleProduct, PublishResult
from app.services.wechat.service import WechatPublishOrchestrator
from app.db.crud import get_random_published_articles
from app.db.engine import get_db_session
from app.services.wechat.reading_guide import build_reading_guide_html

logger = logging.getLogger("autowz.publish.wechat")

# 视为"成功"的微信发布状态(含仅草稿模式)
_OK_STATUSES = {"success", "publish_success", "draft_created"}


class WechatChannel(Channel):
    name = "wechat"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.orchestrator = WechatPublishOrchestrator()

    async def is_ready(self) -> bool:
        s = self.settings
        return bool(getattr(s, "wechat_app_id", "") and getattr(s, "wechat_app_secret", ""))

    async def publish(self, product: ArticleProduct, *, as_draft: bool = True) -> PublishResult:
        # 固定草稿模式，避免任何渠道绕过人工审核直接发布。
        content_html = product.content_html
        with get_db_session() as session:
            guide_articles = get_random_published_articles(
                session, count=3, exclude_article_id=product.article_id
            )
        guide_html = build_reading_guide_html(guide_articles)
        if guide_html:
            content_html += guide_html

        payload = WechatArticlePayload(
            title=re.sub(r"[*_`#]+", "", product.title or "").strip(),
            author=product.author or getattr(self.settings, "content_author", "现象观察"),
            digest=product.digest,
            content=content_html,
            content_source_url=product.source_url or "",
            thumb_media_id="TO_BE_FILLED",  # 由 orchestrator 上传封面后填充
            need_open_comment=self.settings.default_comment_open,
            only_fans_can_comment=self.settings.default_fans_comment_only,
        )
        result = await self.orchestrator.publish_article(
            payload, product.cover_path, force_draft=True
        )
        return PublishResult(
            channel=self.name,
            ok=result.publish_status in _OK_STATUSES,
            status=result.publish_status,
            url=result.article_url,
            draft_id=result.draft_media_id,
            error=result.error_message,
            raw=result.model_dump(),
        )
