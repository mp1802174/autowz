"""百家号渠道(Playwright + 登录态 + JWT token)。

发布流程:
  打开编辑页(获取页面上下文)→ 从 localStorage 取 JWT token →
  page.evaluate 调 /pcui/article/save(带 token header)。
  - 固定 is_draft=1 保存草稿；真实发布必须人工审核后手动操作
  百家号的 save API 需要在 request header 中传 token 字段(JWT),
  该 token 由页面 JS 在加载时写入 localStorage['edit-token']。
"""
from __future__ import annotations

import json
import logging
import re
import base64
import os
import uuid
from pathlib import Path
from urllib.parse import quote

from app.services.publish.channels.playwright_base import PlaywrightChannel
from app.services.publish.product import ArticleProduct, PublishResult

logger = logging.getLogger("autowz.publish.baijiahao")


class BaijiahaoChannel(PlaywrightChannel):
    name = "baijiahao"
    home_url = "https://baijiahao.baidu.com/builder/rc/home"
    state_filename = "baijiahao_state.json"
    edit_url = "https://baijiahao.baidu.com/builder/rc/edit?type=news"

    @staticmethod
    def _strip_wechat_guide(html: str) -> str:
        return re.sub(
            r'<section\b[^>]*>.*?精彩文章导读.*?</section>\s*',
            "",
            html or "",
            flags=re.I | re.S,
        )

    @staticmethod
    def _image_size(cover_path: str | None) -> tuple[int, int]:
        if cover_path and Path(cover_path).exists():
            try:
                from PIL import Image
                with Image.open(cover_path) as img:
                    return img.size
            except Exception:
                logger.warning("百家号: 读取封面尺寸失败,使用默认尺寸", exc_info=True)
        return 900, 383

    @staticmethod
    def _cover_crop(width: int, height: int) -> dict:
        """百家号封面裁剪比例约为 372:248(3:2)。"""
        target_w, target_h = 372, 248
        if width <= 0 or height <= 0:
            width, height = 900, 383
        if width / height > target_w / target_h:
            crop_h = max(height, target_h)
            crop_w = round(crop_h * target_w / target_h)
            x, y = 0, 0
        else:
            crop_w = max(width, target_w)
            crop_h = round(crop_w * target_h / target_w)
            x = max(round(width / 2 - crop_w / 2), 0)
            y = max(round(height / 2 - crop_h / 2), 0)
        return {"x": x, "y": y, "width": crop_w, "height": crop_h}

    @staticmethod
    def _bjh_image_html(image_url: str, width: int, height: int) -> str:
        """生成百家号编辑器可识别的正文图片。

        只写普通 <img src> 时，草稿正文能显示图片，但手机端“添加封面”
        可能提示“正文中无可用图片”。百家号前端会读取 data-w/data-h 和
        data-bjh-params，并优先读取 data-ai-copilot-set-as-cover=1。
        """
        caption_id = f"cap-{uuid.uuid4()}"
        params = quote(json.dumps({"is_legal": 0}, ensure_ascii=False, separators=(",", ":")))
        return (
            f'<p class="bjh-image-container" data-bjh-caption-id="{caption_id}" '
            f'data-bjh-caption-text="">'
            f'<img src="{image_url}" data-bjh-type="IMG" data-w="{width}" data-h="{height}" '
            f'data-bjh-params="{params}" data-ai-copilot-set-as-cover="1">'
            f'</p><p class="bjh-image-caption" data-bjh-caption-for="{caption_id}"></p>'
        )

    @classmethod
    def _to_html(
        cls,
        product: ArticleProduct,
        image_url: str = "",
        image_size: tuple[int, int] = (900, 383),
    ) -> str:
        if product.content_html:
            html = cls._strip_wechat_guide(product.content_html)
            html = re.sub(r"<img\b[^>]*>", "", html, flags=re.I)
            if image_url:
                html = cls._bjh_image_html(image_url, *image_size) + html
            return html
        text = product.content_md or ""
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        html = "".join(f"<p>{p}</p>" for p in paragraphs)
        if image_url:
            html = cls._bjh_image_html(image_url, *image_size) + html
        return html

    @classmethod
    def _cover_fields(cls, image_url: str, origin_url: str, image_size: tuple[int, int]) -> tuple[list, list, str]:
        if not image_url:
            return [], [], "zero"
        width, height = image_size
        cover_images = [{
            "src": image_url,
            "cropData": cls._cover_crop(width, height),
            "machine_chooseimg": 0,
            "isLegal": 0,
        }]
        cover_images_map = [{"src": image_url, "origin_src": origin_url or image_url}]
        return cover_images, cover_images_map, "one"

    async def _upload_image(self, page, cover_path: str | None, token: str) -> dict:
        if not cover_path or not Path(cover_path).exists():
            return {}
        b64 = base64.b64encode(Path(cover_path).read_bytes()).decode()
        name = os.path.basename(cover_path)
        return await page.evaluate(
            """async ([b64, name, token]) => {
                const bin = atob(b64);
                const arr = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
                const file = new File([arr], name, {type: 'image/jpeg'});
                const fd = new FormData();
                fd.append('media', file);
                fd.append('type', 'image');
                fd.append('app_id', '1');
                fd.append('is_events', '');
                fd.append('article_type', 'news');
                const resp = await fetch('/materialui/picture/uploadProxy', {
                    method: 'POST',
                    headers: {'token': token || ''},
                    body: fd,
                    credentials: 'include',
                });
                const data = await resp.json();
                if (data.errno !== 0) throw new Error(JSON.stringify(data));
                return data.ret || {};
            }""",
            [b64, name, token],
        )

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

        image = await self._upload_image(page, product.cover_path, jwt_token)
        image_url = image.get("https_url") or image.get("no_waterlog_bos_url") or image.get("bos_url") or ""
        if not image_url:
            # 封面缺失会导致草稿正文无内嵌图,手机端发布时无法设封面("正文中无可用图片")。
            # 不否决保存(留草稿便于人工补图),但必须暴露,避免静默产出无图草稿。
            logger.warning(
                "百家号: 未取得封面图 url(cover_path=%s, exists=%s),"
                "草稿正文将无图、手机端无法设封面发布",
                product.cover_path,
                bool(product.cover_path and Path(product.cover_path).exists()),
            )

        image_size = self._image_size(product.cover_path)
        title = re.sub(r"[*_`#]+", "", product.title or "").strip()[:40]
        content = self._to_html(product, image_url=image_url, image_size=image_size)
        cover_images, cover_images_map, cover_layout = self._cover_fields(
            image_url,
            image.get("org_url") or image_url,
            image_size,
        )

        # 永远保存草稿，真实发布必须人工审核后手动操作。
        draft_flag = "1"

        result = await page.evaluate(
            """async ([title, content, token, isDraft, coverImages, coverImagesMap, coverLayout]) => {
                const fd = new URLSearchParams();
                fd.append('title', title);
                fd.append('content', content);
                fd.append('type', 'news');
                fd.append('is_draft', isDraft);
                fd.append('cover_images', JSON.stringify(coverImages));
                fd.append('_cover_images_map', JSON.stringify(coverImagesMap));
                fd.append('cover_images_map', JSON.stringify(coverImagesMap));
                fd.append('cover_layout', coverLayout);

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
            [title, content, jwt_token, draft_flag, cover_images, cover_images_map, cover_layout],
        )

        errno = result.get("errno")
        errmsg = result.get("errmsg", "")
        ret = result.get("ret") or {}
        article_id = str(ret.get("article_id") or ret.get("id") or "")
        app_id = str(ret.get("app_id") or "")

        if errno == 0:
            logger.info("百家号草稿已保存 article_id=%s", article_id or "(auto)")
            return PublishResult(
                channel=self.name, ok=True, status="draft_saved",
                draft_id=article_id or "ok",
                raw=result,
            )

        logger.error("百家号发布失败 errno=%s errmsg=%s", errno, errmsg)
        return PublishResult(
            channel=self.name, ok=False, status="publish_failed",
            error=f"百家号发布失败 errno={errno} errmsg={errmsg}",
            raw=result,
        )
