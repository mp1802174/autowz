"""头条号渠道(Playwright + 登录态)。

发布流程:
  打开图文发布页(获取页面上下文与 cookie)→
  用 page.evaluate 直接调用 /mp/agw/article/publish 接口。
  - 固定 save=0 保存草稿；真实发布必须人工审核后手动操作

TODO(P1):正文改富文本(HTML/图片)而非纯文本;ai_disclosure 注入方式优化。
"""
from __future__ import annotations

import json
import logging
import re
import base64
import os
from pathlib import Path

from app.services.publish.channels.playwright_base import PlaywrightChannel
from app.services.publish.product import ArticleProduct, PublishResult

logger = logging.getLogger("autowz.publish.toutiao")


class ToutiaoChannel(PlaywrightChannel):
    name = "toutiao"
    home_url = "https://mp.toutiao.com/"
    state_filename = "toutiao_state.json"
    publish_url = "https://mp.toutiao.com/profile_v4/graphic/publish"
    # 头条前端枚举: PUBLISH=0/DRAFT=1，但提交字段 save 的语义相反：
    # save=1 是发表，save=0 才是保存草稿。
    DRAFT_SAVE_MODE = "0"

    @staticmethod
    def _strip_wechat_guide(html: str) -> str:
        return re.sub(
            r'<section\b[^>]*>.*?精彩文章导读.*?</section>\s*',
            "",
            html or "",
            flags=re.I | re.S,
        )

    @classmethod
    def _to_html(cls, product: ArticleProduct, image_url: str = "") -> str:
        """把内容转为简单 HTML 段落(头条 publish 接口需要 HTML)。"""
        if product.content_html:
            html = cls._strip_wechat_guide(product.content_html)
            html = re.sub(r"<img\b[^>]*>", "", html, flags=re.I)
            if image_url:
                html = f'<p><img src="{image_url}" /></p>' + html
            return html
        text = product.content_md or ""
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        html = "".join(f"<p>{p}</p>" for p in paragraphs)
        if image_url:
            html = f'<p><img src="{image_url}" /></p>' + html
        return html

    async def _upload_image(self, page, cover_path: str | None) -> dict:
        if not cover_path or not Path(cover_path).exists():
            return {}
        b64 = base64.b64encode(Path(cover_path).read_bytes()).decode()
        name = os.path.basename(cover_path)
        return await page.evaluate(
            """async ([b64, name]) => {
                const bin = atob(b64);
                const arr = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                const file = new File([arr], name, {type: 'image/jpeg'});
                const fd = new FormData();
                fd.append('image', file, name);
                const resp = await fetch(
                    '/spice/image?upload_source=20020003&aid=1231&device_platform=web&need_cover_url=1',
                    {method: 'POST', body: fd, credentials: 'include'}
                );
                const data = await resp.json();
                if (data.code !== 0) throw new Error(JSON.stringify(data));
                return data.data || {};
            }""",
            [b64, name],
        )

    async def _do_publish(self, page, product: ArticleProduct, *, as_draft: bool) -> PublishResult:
        await page.goto(self.publish_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        image = await self._upload_image(page, product.cover_path)
        image_url = image.get("image_url") or image.get("origin_image_url") or ""
        image_uri = image.get("image_uri") or image.get("origin_image_uri") or ""

        title = re.sub(r"[*_`#]+", "", product.title or "").strip()[:30]
        content = self._to_html(product, image_url=image_url)
        word_cnt = len(re.sub(r"<[^>]+>", "", content))
        covers = [{
            "uri": image_uri,
            "url": image.get("cover_url") or image_url,
            "width": image.get("image_width") or 900,
            "height": image.get("image_height") or 383,
        }] if image_uri else []

        extra = json.dumps({
            "content_source": 100000000402,
            "content_word_cnt": word_cnt,
            "is_multi_title": 0,
            "sub_titles": [],
            "gd_ext": {
                "entrance": "",
                "from_page": "publisher_mp",
                "enter_from": "PC",
                "device_platform": "mp",
                "is_message": 0,
            },
            "tuwen_wtt_transfer_switch": "1",
        }, ensure_ascii=False)

        # 永远保存草稿，真实发布必须人工审核后手动操作。
        save_mode = self.DRAFT_SAVE_MODE

        result = await page.evaluate(
            """async ([title, content, extra, save, covers]) => {
                const fd = new URLSearchParams();
                fd.append('title', title);
                fd.append('content', content);
                fd.append('save', save);
                fd.append('source', '29');
                fd.append('article_ad_type', '2');
                fd.append('claim_exclusive', '0');
                fd.append('praise', '0');
                fd.append('disable_praise', '0');
                fd.append('is_fans_article', '0');
                fd.append('govern_forward', '0');
                fd.append('timer_status', '0');
                fd.append('is_refute_rumor', '0');
                fd.append('activity_tag', '0');
                fd.append('tree_plan_article', '0');
                fd.append('trends_writing_tag', '0');
                fd.append('pgc_feed_covers', JSON.stringify(covers));
                fd.append('draft_form_data', JSON.stringify({coverType: covers.length ? 1 : 2}));
                fd.append('mp_editor_stat', '{}');
                fd.append('search_creation_info', JSON.stringify({
                    searchTopOne: 0, abstract: '', clue_id: ''
                }));
                fd.append('extra', extra);

                const resp = await fetch('/mp/agw/article/publish?source=mp&type=article&aid=1231&mp_publish_ab_val=0', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: fd.toString(),
                });
                return await resp.json();
            }""",
            [title, content, extra, save_mode, covers],
        )

        err_no = result.get("err_no", result.get("code"))
        data = result.get("data") or {}
        pgc_id = str(data.get("pgc_id") or data.get("pgcId") or "0")
        item_id = str(data.get("item_id") or "")
        msg = result.get("message") or result.get("reason", "")

        if err_no == 0 and pgc_id not in ("0", ""):
            logger.info("头条草稿已保存 pgc_id=%s", pgc_id)
            return PublishResult(channel=self.name, ok=True, status="draft_saved", draft_id=pgc_id, raw=result)

        logger.error("头条发布失败 err_no=%s msg=%s", err_no, msg)
        return PublishResult(
            channel=self.name, ok=False, status="publish_failed",
            error=f"头条发布失败 err_no={err_no} msg={msg}",
            raw=result,
        )
