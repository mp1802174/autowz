"""头条号渠道(Playwright + 登录态)。

发布流程:
  打开图文发布页(获取页面上下文与 cookie)→
  用 page.evaluate 直接调用 /mp/agw/article/publish 接口。
  - 固定 save=1 直接发布(经用户 2026-06-24 明确授权)

⚠️ 为什么是直接发布而非保存草稿:
  头条对"存草稿(save=0)"接口加了反自动化校验,Playwright 这类自动化浏览器一律
  返回 7050"保存失败"(真实浏览器可成功;影刀 RPA 同样现象)。而 save=1 直接发布
  校验维度不同、可成功。详见仓库 7050.md §10。
  质量由上游质量闸(quality/checker.py)+ 风控(guard)兜底:走到发布这步的稿件已过闸。

TODO(P1):正文改富文本(HTML/图片)而非纯文本;ai_disclosure 注入方式优化。
"""
from __future__ import annotations

import asyncio
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
    # 提交字段 save 的语义: save=1 直接发表, save=0 保存草稿。
    # 头条对自动化环境的存草稿(save=0)风控返回 7050,故服务器侧只能用 save=1 直接发布。
    PUBLISH_SAVE_MODE = "1"

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

        # 读取头条当前账号的默认投放广告字段；2026-06 实测新权限号默认值为 3，
        # 继续硬编码旧值 2 会导致草稿保存返回 7050。读取失败则按当前默认兜底为 3。
        article_ad_type = await self._get_default_article_ad_type(page)

        # 发布 API 调用(可重试); page.goto 和上传不走重试(超时/网络类异常由上层 PlaywrightChannel 兜底)
        for attempt in (1, 2):
            result = await self._call_publish_api(page, title, content, word_cnt, covers, article_ad_type)
            err_no = result.get("err_no", result.get("code"))
            data = result.get("data") or {}
            pgc_id = str(data.get("pgc_id") or data.get("pgcId") or "")
            msg = result.get("message") or result.get("reason", "")

            if err_no == 0 and pgc_id not in ("0", ""):
                logger.info("头条已直接发布 pgc_id=%s attempt=%d", pgc_id, attempt)
                return PublishResult(channel=self.name, ok=True, status="published",
                                     draft_id=pgc_id, raw=result)

            if attempt == 1:
                logger.warning("头条发布失败 attempt=1 err_no=%s msg=%s, 2秒后重试", err_no, msg)
                await asyncio.sleep(2)

        logger.error("头条发布失败(已重试1次) err_no=%s msg=%s", err_no, msg)
        return PublishResult(
            channel=self.name, ok=False, status="publish_failed",
            error=f"头条发布失败(已重试) err_no={err_no} msg={msg}",
            raw=result,
        )

    async def _get_default_article_ad_type(self, page) -> str:
        try:
            data = await page.evaluate(
                """async () => {
                    const resp = await fetch('/mp/agw/article/new?article_type=0&format=json&compat=1&column_no=', {
                        credentials: 'include'
                    });
                    return await resp.json();
                }"""
            )
            value = (data.get("data") or {}).get("article_ad_type")
            if value is not None:
                return str(value)
        except Exception as exc:
            logger.warning("读取头条 article_ad_type 默认值失败，使用 3 兜底: %s", exc)
        return "3"

    async def _call_publish_api(self, page, title: str, content: str, word_cnt: int, covers: list, article_ad_type: str) -> dict:
        """调用头条发布 API(抽取为独立方法以便重试)。"""
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

        # save=1 直接发布(用户授权)；存草稿在自动化环境被头条 7050 拒，详见类注释。
        save_mode = self.PUBLISH_SAVE_MODE

        return await page.evaluate(
            """async ([title, content, extra, save, covers, articleAdType]) => {
                const fd = new URLSearchParams();
                fd.append('title', title);
                fd.append('content', content);
                fd.append('save', save);
                fd.append('source', '29');
                fd.append('article_ad_type', articleAdType);
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
            [title, content, extra, save_mode, covers, article_ad_type],
        )

