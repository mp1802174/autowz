"""头条号渠道(Playwright + 登录态)。

实测摸清的发布流程(2026-06-19):
  打开图文发布页 → 移除右侧"AI 助手抽屉"(否则遮挡正文编辑器)→
  标题填入 textarea → 正文填入 .ProseMirror(字节 SYL 编辑器)→
  失焦触发头条"自动保存草稿" → 监听 mp/agw/article/publish 响应判断结果。
始终只存草稿(从不点"预览并发布"),草稿优先、安全。

⚠️ 账号需完成实名/完善信息,否则保存接口返回 err_no=7050「保存失败」(实测)。
TODO(P1):正文改富文本(HTML/图片)而非纯文本;ai_disclosure 注入方式优化。
"""
from __future__ import annotations

import asyncio
import logging
import re

from app.services.publish.channels.playwright_base import PlaywrightChannel
from app.services.publish.product import ArticleProduct, PublishResult

logger = logging.getLogger("autowz.publish.toutiao")


class ToutiaoChannel(PlaywrightChannel):
    name = "toutiao"
    home_url = "https://mp.toutiao.com/"
    state_filename = "toutiao_state.json"
    publish_url = "https://mp.toutiao.com/profile_v4/graphic/publish"

    @staticmethod
    def _to_text(product: ArticleProduct) -> str:
        """P0:把内容转纯文本填入(富文本/图片留 P1)。"""
        txt = product.content_md or re.sub(r"<[^>]+>", "", product.content_html or "")
        return re.sub(r"\n{3,}", "\n\n", txt).strip()

    async def _do_publish(self, page, product: ArticleProduct, *, as_draft: bool) -> PublishResult:
        save: dict = {}

        async def on_resp(r):
            if "agw/article/publish" in r.url:
                try:
                    j = await r.json()
                    save["err_no"] = j.get("err_no")
                    save["message"] = j.get("message")
                    save["pgc_id"] = (j.get("data") or {}).get("pgc_id")
                except Exception:
                    pass

        page.on("response", lambda r: asyncio.create_task(on_resp(r)))

        await page.goto(self.publish_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(7000)
        # 移除右侧 AI 助手抽屉(否则遮挡正文编辑器点击)
        await page.evaluate(
            "()=>{document.querySelectorAll('.byte-drawer-mask,.ai-assistant-drawer').forEach(e=>e.remove())}"
        )
        # 标题(逐字真实输入,触发头条 onChange)
        tb = page.locator('textarea[placeholder*="请输入文章标题"]').first
        await tb.click()
        await tb.press_sequentially((product.title or "")[:30], delay=10)
        # 正文(P0 纯文本)
        body_text = self._to_text(product)
        if product.ai_disclosure:
            body_text += "\n\n(本文由 AI 辅助生成)"
        ed = page.locator(".ProseMirror").first
        await ed.click()
        await page.keyboard.insert_text(body_text)
        await page.mouse.click(5, 5)  # 失焦,触发自动保存草稿

        # 等待头条自动保存结果
        for _ in range(15):
            await page.wait_for_timeout(2000)
            if save.get("err_no") is not None:
                break

        err_no = save.get("err_no")
        pgc_id = str(save.get("pgc_id") or "0")
        if err_no == 0 or pgc_id not in ("0", ""):
            logger.info("头条草稿已保存 pgc_id=%s", pgc_id)
            return PublishResult(channel=self.name, ok=True, status="draft_saved", draft_id=pgc_id)

        msg = save.get("message") or "未捕获到保存结果"
        return PublishResult(
            channel=self.name, ok=False, status="save_failed",
            error=f"头条保存失败 err_no={err_no} msg={msg}",
            skipped_reason="账号未实名/完善信息时常见 err_no=7050;请先在头条号完成认证",
        )
