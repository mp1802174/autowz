"""为公众号《今天怎么看》生成主笔人设头像。

人设：45 岁资深时事评论人，中传新闻硕士、中共党员、国学功底深厚。
"""
import asyncio
import sys
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.services.wechat.cover_generator import _generate_via_chat_completion  # noqa: E402

OUTPUT_DIR = Path(__file__).parent.parent / "assets" / "avatars"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPT = (
    "Professional portrait illustration of a 45-year-old Chinese male senior "
    "journalist and political commentator. Clean modern editorial style, "
    "warm and intellectual expression, slightly graying short black hair, "
    "wearing a dark navy blazer over a light shirt, no tie. "
    "Soft natural studio lighting, neutral warm beige background with subtle "
    "abstract bookshelf bokeh suggesting a study room. "
    "Calm, thoughtful, approachable demeanor — looking slightly off-camera. "
    "Style: refined semi-realistic illustration, clean lines, magazine-quality. "
    "Square composition, head-and-shoulders, centered, suitable for a WeChat "
    "official account avatar. "
    "Strictly no text, no logos, no flags, no political symbols, no uniforms, "
    "no party emblems, no government badges. Tasteful, neutral, dignified."
)


async def generate() -> Path:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=120.0) as client:
        image_bytes = await _generate_via_chat_completion(client, settings, PROMPT)

    img = Image.open(BytesIO(image_bytes))

    # 裁正方形（居中）
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
    # 微信头像建议 ≥ 144x144，主流上传 640x640
    img = img.resize((640, 640), Image.Resampling.LANCZOS)

    out = OUTPUT_DIR / "avatar_zhiwei_guanlan.jpg"
    img.save(out, "JPEG", quality=92)
    print(f"已保存: {out}")
    return out


if __name__ == "__main__":
    asyncio.run(generate())
