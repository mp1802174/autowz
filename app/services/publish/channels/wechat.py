"""WechatChannel —— 把现有 app/services/wechat 发布编排包装成统一 Channel。

行为与现状完全一致:草稿 / 自动发布仍由 settings.wechat_enable_auto_publish 决定,
本类只做接口适配(ArticleProduct → WechatArticlePayload),不改动现有微信发布逻辑。
"""
from __future__ import annotations

import logging

from app.core.config import get_settings
from app.models.schemas import WechatArticlePayload
from app.services.publish.base import Channel
from app.services.publish.product import ArticleProduct, PublishResult
from app.services.wechat.service import WechatPublishOrchestrator

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
        # 注:微信的草稿/发布由 settings.wechat_enable_auto_publish 控制,
        # as_draft 在此不强制改变现有行为(保持现状,P0 不动主流程)。
        payload = WechatArticlePayload(
            title=product.title,
            author=product.author or getattr(self.settings, "content_author", "现象观察"),
            digest=product.digest,
            content=product.content_html,
            content_source_url=product.source_url or "",
            thumb_media_id="TO_BE_FILLED",  # 由 orchestrator 上传封面后填充
            need_open_comment=self.settings.default_comment_open,
            only_fans_can_comment=self.settings.default_fans_comment_only,
        )
        result = await self.orchestrator.publish_article(payload, product.cover_path)
        return PublishResult(
            channel=self.name,
            ok=result.publish_status in _OK_STATUSES,
            status=result.publish_status,
            url=result.article_url,
            draft_id=result.draft_media_id,
            error=result.error_message,
            raw=result.model_dump(),
        )
