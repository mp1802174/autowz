import logging
from pathlib import Path

from app.services.wechat.client import WechatClient
from app.services.wechat.token_service import WechatTokenService

logger = logging.getLogger("autowz.wechat.material")


class WechatMaterialService:
    def __init__(
        self,
        token_service: WechatTokenService | None = None,
        client: WechatClient | None = None,
    ) -> None:
        self.client = client or WechatClient()
        self.token_service = token_service or WechatTokenService(self.client)

    async def upload_image(self, image_path: str | None) -> dict:
        if not image_path:
            logger.warning("未提供封面图片，使用 mock media_id")
            return {"media_id": "mock-thumb-media-id", "url": ""}

        path = Path(image_path)
        if not path.exists():
            raise ValueError(f"封面图片不存在: {image_path}")

        token = await self.token_service.get_access_token()
        if token == "mock-access-token":
            logger.info("mock 模式，跳过真实上传")
            return {"media_id": f"mock-{path.stem}", "url": f"file://{path}"}

        data = await self.client.post_multipart(
            "/cgi-bin/material/add_material",
            params={"access_token": token, "type": "image"},
            file_path=path,
        )
        media_id = data.get("media_id", "")
        url = data.get("url", "")
        logger.info("封面上传成功: media_id=%s", media_id)
        return {"media_id": media_id, "url": url}

    async def upload_temp_image(self, image_path: str | None) -> dict:
        """上传图片用于正文插入（使用图文消息专用接口）。"""
        if not image_path:
            logger.warning("未提供图片")
            return {"url": ""}

        path = Path(image_path)
        if not path.exists():
            raise ValueError(f"图片不存在: {image_path}")

        token = await self.token_service.get_access_token()
        if token == "mock-access-token":
            logger.info("mock 模式，跳过真实上传")
            return {"url": f"file://{path}"}

        # 使用图文消息专用的图片上传接口
        data = await self.client.post_multipart(
            "/cgi-bin/media/uploadimg",
            params={"access_token": token},
            file_path=path,
        )
        url = data.get("url", "")
        logger.info("图文消息图片上传成功: url=%s", url)
        return {"url": url}
