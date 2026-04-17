import asyncio
import logging
import tempfile
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings

logger = logging.getLogger("autowz.wechat.cover")

# 微信公众号推荐封面尺寸 2.35:1
COVER_WIDTH = 900
COVER_HEIGHT = 383


async def generate_cover_async(title: str, output_path: str | None = None) -> str:
    """生成封面图（异步版本），优先使用 AI 生成，失败则回退到文字封面。"""
    try:
        return await _generate_ai_cover(title, output_path)
    except Exception as exc:
        logger.warning("AI 封面生成失败，回退到文字封面: %s", exc)
        return _generate_text_cover(title, output_path)


def generate_cover(title: str, output_path: str | None = None) -> str:
    """生成封面图（同步版本），仅生成文字封面。"""
    return _generate_text_cover(title, output_path)


async def _generate_ai_cover(title: str, output_path: str | None = None) -> str:
    """使用 AI 生成封面图。"""
    settings = get_settings()

    # 构建 prompt：简洁、视觉化、适合新闻评论
    prompt = (
        f"A minimalist, professional cover image for a Chinese news commentary article titled '{title}'. "
        f"Style: clean, modern, abstract geometric shapes or subtle gradients. "
        f"Colors: deep blue, gray, white. No text, no people, no complex scenes. "
        f"Aspect ratio 2.35:1 (900x383px)."
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.x.ai/v1/images/generations",
            headers={"Authorization": f"Bearer {settings.xai_api_key}"},
            json={
                "model": settings.xai_image_model,
                "prompt": prompt,
                "n": 1,
            },
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("data") or not data["data"][0].get("url"):
            raise ValueError("AI 返回的图片 URL 为空")

        image_url = data["data"][0]["url"]

        # 下载图片
        img_response = await client.get(image_url)
        img_response.raise_for_status()

        # 保存并裁剪为 2.35:1
        if output_path:
            out = Path(output_path)
        else:
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, prefix="autowz_cover_ai_")
            out = Path(tmp.name)
            tmp.close()

        # 加载图片并裁剪
        img = Image.open(BytesIO(img_response.content))
        img = _crop_to_cover_ratio(img)
        img.save(str(out), "JPEG", quality=90)

        logger.info("AI 封面图已生成: %s", out)
        return str(out)


def _crop_to_cover_ratio(img: Image.Image) -> Image.Image:
    """裁剪图片为 2.35:1 比例（900x383）。"""
    target_ratio = COVER_WIDTH / COVER_HEIGHT
    current_ratio = img.width / img.height

    if current_ratio > target_ratio:
        # 图片太宽，裁剪左右
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        # 图片太高，裁剪上下
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))

    # 缩放到目标尺寸
    img = img.resize((COVER_WIDTH, COVER_HEIGHT), Image.Resampling.LANCZOS)
    return img


def _generate_text_cover(title: str, output_path: str | None = None) -> str:
    """生成文字封面（兜底方案）。"""
    img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT))
    draw = ImageDraw.Draw(img)

    # 渐变背景（深蓝→深灰）
    for y in range(COVER_HEIGHT):
        r = int(20 + (40 - 20) * y / COVER_HEIGHT)
        g = int(30 + (45 - 30) * y / COVER_HEIGHT)
        b = int(60 + (70 - 60) * y / COVER_HEIGHT)
        draw.line([(0, y), (COVER_WIDTH, y)], fill=(r, g, b))

    # 尝试加载中文字体
    font_title = _load_font(36)
    font_brand = _load_font(20)

    # 绘制标题（自动换行）
    _draw_wrapped_text(draw, title, font_title, COVER_WIDTH - 100, 50, (255, 255, 255))

    # 品牌名
    draw.text(
        (COVER_WIDTH - 180, COVER_HEIGHT - 50),
        "今天怎么看",
        font=font_brand,
        fill=(180, 180, 200),
    )

    # 底部装饰线
    draw.line(
        [(50, COVER_HEIGHT - 70), (COVER_WIDTH - 50, COVER_HEIGHT - 70)],
        fill=(100, 100, 140),
        width=1,
    )

    if output_path:
        out = Path(output_path)
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, prefix="autowz_cover_")
        out = Path(tmp.name)
        tmp.close()

    img.save(str(out), "JPEG", quality=90)
    logger.info("封面图已生成: %s", out)
    return str(out)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """尝试加载系统中文字体。"""
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for fp in font_paths:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    start_y: int,
    fill: tuple,
) -> None:
    """自动换行绘制文本。"""
    lines: list[str] = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] > max_width:
            if current_line:
                lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    y = start_y
    x = 50
    for line in lines[:4]:  # 最多4行
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + 10
