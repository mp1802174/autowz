import logging

from app.core.config import get_settings
from app.models.schemas import WechatArticlePayload, WechatPublishResult
from app.services.wechat.client import WechatClient, TOKEN_EXPIRED_CODES
from app.services.wechat.draft_service import WechatDraftService
from app.services.wechat.exceptions import WechatAPIError
from app.services.wechat.material_service import WechatMaterialService
from app.services.wechat.publish_service import WechatFreePublishService
from app.services.wechat.token_service import WechatTokenService

logger = logging.getLogger("autowz.wechat")


class WechatPublishOrchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()
        # 共享同一个 client 和 token_service 实例
        client = WechatClient()
        self.token_service = WechatTokenService(client)
        self.material_service = WechatMaterialService(self.token_service, client)
        self.draft_service = WechatDraftService(self.token_service, client)
        self.publish_service = WechatFreePublishService(self.token_service, client)

    async def publish_article(
        self,
        payload: WechatArticlePayload,
        cover_image_path: str | None = None,
    ) -> WechatPublishResult:
        try:
            return await self._do_publish(payload, cover_image_path)
        except WechatAPIError as exc:
            if exc.errcode in TOKEN_EXPIRED_CODES:
                logger.warning("Token 过期，刷新后重试: %s", exc)
                self.token_service.invalidate()
                return await self._do_publish(payload, cover_image_path)

            if self.settings.wechat_fallback_to_draft:
                logger.error("发布失败，降级为仅草稿模式: %s", exc)
                return WechatPublishResult(
                    draft_media_id="error",
                    publish_status="fallback_error",
                    fallback_mode="draft_only",
                )
            raise

    async def _do_publish(
        self,
        payload: WechatArticlePayload,
        cover_image_path: str | None,
    ) -> WechatPublishResult:
        # 1. 上传封面（永久素材）
        image_data = await self.material_service.upload_image(cover_image_path)
        payload.thumb_media_id = image_data["media_id"]
        logger.info("封面上传完成，准备插入正文图片，cover_image_path=%s", cover_image_path)

        # 1.5. 上传图片用于正文插入（使用图文消息专用接口）
        if cover_image_path:
            logger.info("开始上传正文图片")
            content_image = await self.material_service.upload_temp_image(cover_image_path)
            content_image_url = content_image.get("url", "")
            logger.info("正文图片上传完成，url=%s", content_image_url)

            if content_image_url and not content_image_url.startswith("file://"):
                # 在正文开头插入封面图（使用微信公众号标准格式）
                # 图片宽高比 2.35:1 (900x383)
                img_tag = (
                    f'<section><section style="display: inline-block;">'
                    f'<img data-ratio="0.4255555555555556" data-src="{content_image_url}" '
                    f'data-type="jpeg" data-w="900">'
                    f'</section></section>'
                )
                logger.info("准备插入图片标签，原内容长度=%d", len(payload.content))
                payload.content = img_tag + payload.content
                logger.info("图片标签已插入，新内容长度=%d，前200字符=%s",
                           len(payload.content), payload.content[:200])
            else:
                logger.warning("图片 URL 无效或为 file:// 协议，跳过插入")
        else:
            logger.warning("未提供 cover_image_path，跳过正文图片插入")

        # 2. 创建草稿
        draft_media_id = await self.draft_service.create_draft(payload)
        logger.info("草稿已创建: %s", draft_media_id)

        if not self.settings.wechat_enable_auto_publish:
            return WechatPublishResult(
                draft_media_id=draft_media_id,
                publish_status="draft_created",
                fallback_mode="draft_only",
            )

        # 3. 提交发布
        publish_id = await self.publish_service.submit_publish(draft_media_id)

        # 4. 轮询状态
        result = await self.publish_service.poll_until_complete(publish_id)
        status_str = result.get("status", "submitted")

        if status_str == "failed" and self.settings.wechat_fallback_to_draft:
            logger.warning("发布失败，保留草稿: %s", draft_media_id)
            return WechatPublishResult(
                draft_media_id=draft_media_id,
                publish_id=publish_id,
                publish_status="publish_failed_draft_kept",
                fallback_mode="draft_only",
            )

        return WechatPublishResult(
            draft_media_id=draft_media_id,
            publish_id=publish_id,
            article_url=result.get("article_url"),
            publish_status=status_str,
            fallback_mode="full_publish",
        )
