"""头条号渠道(Playwright + 登录态)。

发布流程:
  打开图文发布页(获取页面上下文与 cookie)→
  用 page.evaluate 直接调用 /mp/agw/article/publish 接口。
  - as_draft=True: save=1 保存草稿
  - as_draft=False: save=0 直接发布(需账号权限)

TODO(P1):正文改富文本(HTML/图片)而非纯文本;ai_disclosure 注入方式优化。
"""
from __future__ import annotations

import json
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
    def _to_html(product: ArticleProduct) -> str:
        """把内容转为简单 HTML 段落(头条 publish 接口需要 HTML)。"""
        if product.content_html:
            return product.content_html
        text = product.content_md or ""
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        return "".join(f"<p>{p}</p>" for p in paragraphs)

    async def _do_publish(self, page, product: ArticleProduct, *, as_draft: bool) -> PublishResult:
        await page.goto(self.publish_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        title = (product.title or "")[:30]
        content = self._to_html(product)
        word_cnt = len(re.sub(r"<[^>]+>", "", content))

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

        # save=1: 保存草稿, save=0: 直接发布
        save_mode = "1" if as_draft else "0"

        result = await page.evaluate(
            """async ([title, content, extra, save]) => {
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
                fd.append('pgc_feed_covers', '[]');
                fd.append('draft_form_data', JSON.stringify({coverType: 2}));
                fd.append('mp_editor_stat', '{}');
                fd.append('search_creation_info', JSON.stringify({
                    searchTopOne: 0, abstract: '', clue_id: ''
                }));
                fd.append('extra', extra);

                const resp = await fetch('/mp/agw/article/publish', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: fd.toString(),
                });
                return await resp.json();
            }""",
            [title, content, extra, save_mode],
        )

        err_no = result.get("err_no")
        data = result.get("data") or {}
        pgc_id = str(data.get("pgc_id") or "0")
        item_id = str(data.get("item_id") or "")
        msg = result.get("message", "")

        if err_no == 0 and pgc_id not in ("0", ""):
            if as_draft:
                logger.info("头条草稿已保存 pgc_id=%s", pgc_id)
                return PublishResult(channel=self.name, ok=True, status="draft_saved", draft_id=pgc_id)
            else:
                logger.info("头条文章已发布 pgc_id=%s item_id=%s", pgc_id, item_id)
                article_url = f"https://www.toutiao.com/article/{item_id}/" if item_id else ""
                return PublishResult(
                    channel=self.name, ok=True, status="published",
                    draft_id=pgc_id, url=article_url, raw=result
                )

        logger.error("头条发布失败 err_no=%s msg=%s", err_no, msg)
        return PublishResult(
            channel=self.name, ok=False, status="publish_failed",
            error=f"头条发布失败 err_no={err_no} msg={msg}",
            raw=result,
        )
