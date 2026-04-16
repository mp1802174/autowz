import asyncio
import logging

from app.services.wechat.client import WechatClient
from app.services.wechat.token_service import WechatTokenService

logger = logging.getLogger("autowz.wechat.publish")


class WechatFreePublishService:
    def __init__(
        self,
        token_service: WechatTokenService | None = None,
        client: WechatClient | None = None,
    ) -> None:
        self.client = client or WechatClient()
        self.token_service = token_service or WechatTokenService(self.client)

    async def submit_publish(self, media_id: str) -> str:
        token = await self.token_service.get_access_token()
        if token == "mock-access-token":
            mock_id = f"publish-{media_id}"
            logger.info("mock 模式，生成发布ID: %s", mock_id)
            return mock_id

        data = await self.client.post_json(
            "/cgi-bin/freepublish/submit",
            params={"access_token": token},
            json_body={"media_id": media_id},
        )
        publish_id = data.get("publish_id", "")
        logger.info("发布提交成功: publish_id=%s", publish_id)
        return publish_id

    async def get_publish_status(self, publish_id: str) -> dict:
        token = await self.token_service.get_access_token()
        if token == "mock-access-token":
            return {
                "publish_id": publish_id,
                "publish_status": 0,
                "article_url": f"https://mp.weixin.qq.com/s/{publish_id}",
            }

        data = await self.client.post_json(
            "/cgi-bin/freepublish/get",
            params={"access_token": token},
            json_body={"publish_id": publish_id},
        )
        return data

    async def poll_until_complete(
        self, publish_id: str, *, interval: int = 30, max_wait: int = 600,
    ) -> dict:
        """轮询发布状态，直到完成或超时。"""
        elapsed = 0
        while elapsed < max_wait:
            status = await self.get_publish_status(publish_id)
            publish_status = status.get("publish_status", -1)

            # 0=成功, 1=发布中, 2+=失败
            if publish_status == 0:
                article_detail = status.get("article_detail", {})
                items = article_detail.get("item", [])
                article_url = items[0].get("article_url", "") if items else ""
                logger.info("发布成功: %s", article_url)
                return {
                    "status": "success",
                    "article_url": article_url,
                    "raw": status,
                }
            elif publish_status >= 2:
                fail_idx = status.get("fail_idx", [])
                logger.error("发布失败: publish_id=%s, fail_idx=%s", publish_id, fail_idx)
                return {
                    "status": "failed",
                    "article_url": "",
                    "raw": status,
                }

            logger.info("发布进行中，%ds 后再次查询...", interval)
            await asyncio.sleep(interval)
            elapsed += interval

        logger.warning("发布状态轮询超时: publish_id=%s", publish_id)
        return {"status": "timeout", "article_url": "", "raw": {}}
