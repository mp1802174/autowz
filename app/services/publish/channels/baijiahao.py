"""百家号渠道(Playwright + 登录态 + JWT token)。

发布流程:
  打开编辑页(获取页面上下文)→ 从 localStorage 取 JWT token →
  page.evaluate 调 /pcui/article/save(带 token header)。
  - as_draft=True: is_draft=1 保存草稿
  - as_draft=False: is_draft=0 直接发布
  百家号的 save API 需要在 request header 中传 token 字段(JWT),
  该 token 由页面 JS 在加载时写入 localStorage['edit-token']。
"""
from __future__ import annotations

import json
import logging
import re

from app.services.publish.channels.playwright_base import PlaywrightChannel
from app.services.publish.product import ArticleProduct, PublishResult

logger = logging.getLogger("autowz.publish.baijiahao")


class BaijiahaoChannel(PlaywrightChannel):
    name = "baijiahao"
    home_url = "https://baijiahao.baidu.com/builder/rc/home"
    state_filename = "baijiahao_state.json"
    edit_url = "https://baijiahao.baidu.com/builder/rc/edit?type=news"

    @staticmethod
    def _to_html(product: ArticleProduct) -> str:
        if product.content_html:
            return product.content_html
        text = product.content_md or ""
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        return "".join(f"<p>{p}</p>" for p in paragraphs)

    async def _do_publish(self, page, product: ArticleProduct, *, as_draft: bool) -> PublishResult:
        await page.goto(self.edit_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(15000)

        jwt_token = await page.evaluate("""() => {
            try {
                const stored = localStorage.getItem('edit-token');
                if (stored) return JSON.parse(stored);
            } catch(e) {}
            try {
                if (window.__BJH__INIT__AUTH__) return window.__BJH__INIT__AUTH__;
            } catch(e) {}
            return null;
        }""")

        if not jwt_token:
            logger.error("百家号: 无法获取 JWT token,登录态可能已过期")
            return PublishResult(
                channel=self.name, ok=False, status="token_missing",
                error="无法获取百家号 JWT token,请重新导出登录态",
            )

        title = (product.title or "")[:40]
        content = self._to_html(product)
        if product.ai_disclosure:
            content += "<p>(本文由 AI 辅助生成)</p>"

        # is_draft=1: 保存草稿, is_draft=0: 直接发布
        draft_flag = "1" if as_draft else "0"

        result = await page.evaluate(
            """async ([title, content, token, isDraft]) => {
                const fd = new URLSearchParams();
                fd.append('title', title);
                fd.append('content', content);
                fd.append('type', 'news');
                fd.append('is_draft', isDraft);
                fd.append('cover_images', '[]');
                fd.append('cover_layout', '0');

                const resp = await fetch('/pcui/article/save', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'token': token,
                    },
                    body: fd.toString(),
                });
                return await resp.json();
            }""",
            [title, content, jwt_token, draft_flag],
        )

        errno = result.get("errno")
        errmsg = result.get("errmsg", "")
        ret = result.get("ret") or {}
        article_id = str(ret.get("article_id") or ret.get("id") or "")
        app_id = str(ret.get("app_id") or "")

        if errno == 0:
            if as_draft:
                logger.info("百家号草稿已保存 article_id=%s", article_id or "(auto)")
                return PublishResult(
                    channel=self.name, ok=True, status="draft_saved",
                    draft_id=article_id or "ok",
                    raw=result,
                )
            else:
                logger.info("百家号文章已发布 article_id=%s app_id=%s", article_id, app_id)
                article_url = f"https://baijiahao.baidu.com/s?id={app_id}" if app_id else ""
                return PublishResult(
                    channel=self.name, ok=True, status="published",
                    draft_id=article_id, url=article_url,
                    raw=result,
                )

        logger.error("百家号发布失败 errno=%s errmsg=%s", errno, errmsg)
        return PublishResult(
            channel=self.name, ok=False, status="publish_failed",
            error=f"百家号发布失败 errno={errno} errmsg={errmsg}",
            raw=result,
        )
