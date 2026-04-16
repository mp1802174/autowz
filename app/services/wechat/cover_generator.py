import logging
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("autowz.wechat.cover")

# 微信公众号推荐封面尺寸 2.35:1
COVER_WIDTH = 900
COVER_HEIGHT = 383


def generate_cover(title: str, output_path: str | None = None) -> str:
    """生成默认封面图，返回文件路径。"""
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
