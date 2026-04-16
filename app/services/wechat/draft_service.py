import logging

from app.models.schemas import WechatArticlePayload
from app.services.wechat.client import WechatClient
from app.services.wechat.token_service import WechatTokenService

logger = logging.getLogger("autowz.wechat.draft")


class WechatDraftService:
    def __init__(
        self,
        token_service: WechatTokenService | None = None,
        client: WechatClient | None = None,
    ) -> None:
        self.client = client or WechatClient()
        self.token_service = token_service or WechatTokenService(self.client)

    async def create_draft(self, article_payload: WechatArticlePayload) -> str:
        token = await self.token_service.get_access_token()
        if token == "mock-access-token":
            mock_id = f"draft-{abs(hash(article_payload.title)) % 10_000_000}"
            logger.info("mock 模式，生成草稿ID: %s", mock_id)
            return mock_id

        data = await self.client.post_json(
            "/cgi-bin/draft/add",
            params={"access_token": token},
            json_body={
                "articles": [
                    {
                        "title": article_payload.title,
                        "author": article_payload.author,
                        "digest": article_payload.digest,
                        "content": article_payload.content,
                        "content_source_url": article_payload.content_source_url,
                        "thumb_media_id": article_payload.thumb_media_id,
                        "need_open_comment": article_payload.need_open_comment,
                        "only_fans_can_comment": article_payload.only_fans_can_comment,
                    }
                ]
            },
        )
        media_id = data.get("media_id", "")
        logger.info("草稿创建成功: media_id=%s", media_id)
        return media_id
