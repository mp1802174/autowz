"""基于 Playwright + 登录态(storage_state)的渠道基类。

头条 / 百家 / 大鱼等无官方 API 的平台共用此基类:
  加载 storage_state → headless 启动 chromium(带代理)→ 打开平台页面建立登录上下文
  → 子类在页面上下文里完成发布(DOM 自动化 或 page.evaluate 调平台接口)。

登录态导出见 scripts/login_helper.py(在你本地电脑扫码登录,导出 state 传到服务器)。
登录态文件放 app/services/publish/cookies/,已在 .gitignore 中排除,不入库。
"""
from __future__ import annotations

import logging
from typing import Optional
import os
from abc import abstractmethod
from urllib.parse import urlparse

from app.core.config import get_settings
from app.services.publish.base import Channel
from app.services.publish.product import ArticleProduct, PublishResult

logger = logging.getLogger("autowz.publish.playwright")

# app/services/publish/cookies
COOKIES_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "cookies"))


class PlaywrightChannel(Channel):
    """Playwright + 登录态 的渠道基类。子类实现 _do_publish。"""

    name = ""
    home_url = ""        # 用于建立登录上下文 / 检查登录态的页面
    state_filename = ""  # storage_state 文件名(放在 cookies/ 下)

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def state_path(self) -> str:
        return os.path.join(COOKIES_DIR, self.state_filename)

    def _proxy(self) -> Optional[dict]:
        """从环境代理变量构造 Playwright proxy 配置(chromium 不自动读 env 代理)。"""
        raw = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
        if not raw:
            return None
        u = urlparse(raw)
        proxy: dict = {"server": f"{u.scheme}://{u.hostname}:{u.port}"}
        if u.username:
            proxy["username"] = u.username
        if u.password:
            proxy["password"] = u.password
        return proxy

    async def is_ready(self) -> bool:
        """登录态文件存在即视为已配置;有效性在 publish 时由 _do_publish 进一步校验。"""
        return os.path.exists(self.state_path)

    async def publish(self, product: ArticleProduct, *, as_draft: bool = True) -> PublishResult:
        if not os.path.exists(self.state_path):
            return PublishResult(
                channel=self.name, ok=False, status="no_login_state",
                skipped_reason=f"缺少登录态 {self.state_path};请用 scripts/login_helper.py 登录导出",
            )
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, proxy=self._proxy())
            context = await browser.new_context(storage_state=self.state_path)
            try:
                page = await context.new_page()
                return await self._do_publish(page, product, as_draft=as_draft)
            except Exception as exc:
                logger.exception("%s 发布异常", self.name)
                return PublishResult(channel=self.name, ok=False, status="error", error=str(exc))
            finally:
                await context.close()
                await browser.close()

    @abstractmethod
    async def _do_publish(self, page, product: ArticleProduct, *, as_draft: bool) -> PublishResult:
        """在已登录的页面上下文里完成发布。子类实现(各平台差异)。"""
        ...
