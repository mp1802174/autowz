import logging
from time import time

from app.core.config import get_settings
from app.services.wechat.client import WechatClient
from app.services.wechat.exceptions import WechatAPIError

logger = logging.getLogger("autowz.wechat.token")


class WechatTokenService:
    def __init__(self, client: WechatClient | None = None) -> None:
        self.settings = get_settings()
        self.client = client or WechatClient()
        self._cached_token: str | None = None
        self._expires_at: float = 0

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        now = time()
        if not force_refresh and self._cached_token and now < self._expires_at - 300:
            return self._cached_token

        if not self.settings.wechat_app_id or not self.settings.wechat_app_secret:
            logger.warning("未配置微信凭据，使用 mock token")
            return "mock-access-token"

        try:
            data = await self.client.get(
                "/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": self.settings.wechat_app_id,
                    "secret": self.settings.wechat_app_secret,
                },
            )
            self._cached_token = data["access_token"]
            self._expires_at = now + int(data.get("expires_in", 7200))
            logger.info("access_token 获取成功，%ds 后过期", int(self._expires_at - now))
            return self._cached_token
        except WechatAPIError as exc:
            logger.error("获取 access_token 失败: %s", exc)
            if self._cached_token:
                logger.warning("使用缓存的旧 token")
                return self._cached_token
            raise

    def invalidate(self) -> None:
        """使当前 token 失效，下次调用会强制刷新。"""
        self._cached_token = None
        self._expires_at = 0
