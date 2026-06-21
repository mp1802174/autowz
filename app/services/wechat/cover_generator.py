import base64
import json
import logging
import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings

logger = logging.getLogger("autowz.wechat.cover")

# 微信公众号推荐封面尺寸 2.35:1
COVER_WIDTH = 900
COVER_HEIGHT = 383


async def generate_cover_async(
    title: str,
    output_path: Optional[str] = None,
    content: Optional[str] = None,
) -> str:
    """生成封面图（异步版本）。

    必须使用配置的 AI 图片服务生成；失败时抛错，避免静默发布纯色文字占位图。
    """
    return await _generate_ai_cover(title, output_path, content=content)


def generate_cover(title: str, output_path: Optional[str] = None) -> str:
    """生成封面图（同步版本），仅生成文字封面。"""
    return _generate_text_cover(title, output_path)


async def _generate_ai_cover(
    title: str,
    output_path: Optional[str] = None,
    content: Optional[str] = None,
) -> str:
    """使用 AI 生成封面图。"""
    settings = get_settings()

    clean_title = title.replace("今天怎么看｜", "").replace("今天怎么看|", "")

    # 构建 prompt：根据标题生成相关场景图片
    prompt = (
        f"Create a professional, visually striking cover image for a Chinese news article about: {clean_title}. "
        f"Style: photorealistic or modern illustration, clean composition, cinematic lighting. "
        f"Focus on the main subject matter mentioned in the title. "
        f"The image must include concrete visual objects directly related to the key words in the title; "
        f"for example, if the title mentions investment gold, include investment gold bars, and if it mentions kites, include kites. "
        f"Colors: vibrant but professional, suitable for news media. "
        f"Absolutely no text, letters, numbers, logos, captions, labels, or watermarks anywhere in the image. "
        f"High quality, 16:9 aspect ratio."
    )

    timeout = httpx.Timeout(180.0, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        image_bytes = await _generate_via_chat_completion(client, settings, prompt)

        out = _prepare_output_path(output_path, suffix=".jpg", prefix="autowz_cover_ai_")
        img = Image.open(BytesIO(image_bytes))
        img = _crop_to_cover_ratio(img)
        img.save(str(out), "JPEG", quality=90)

        logger.info("AI 封面图已生成: %s", out)
        return str(out)


async def _generate_via_chat_completion(
    client: httpx.AsyncClient,
    settings: Any,
    prompt: str,
) -> bytes:
    """Use the configured SenseNova chat-completions endpoint to generate an image.

    Some OpenAI-compatible image/chat gateways return an image in the top-level
    ``data`` array, while multimodal chat endpoints often attach it to
    ``choices[].message`` as a URL, base64 payload, data URI, or JSON string.
    The parser below accepts all of those shapes so the project is not tied to
    a single vendor-specific response format.
    """
    providers = _build_image_providers(settings)
    if not providers:
        raise ValueError("图片生成 API Key 未配置")

    errors: List[str] = []
    for provider in providers:
        label = f"{provider.get('name') or '?'}/{provider['model']}"
        try:
            logger.info(
                "Generating cover image via %s (%s)",
                label,
                _redact_url(provider["api_url"]),
            )
            return await _generate_with_provider(client, provider, prompt)
        except Exception as exc:
            error = f"{label}: {exc}"
            errors.append(error)
            logger.warning("Image provider failed, trying fallback: %s", error)

    raise ValueError("所有图片生成模型均失败: " + " | ".join(errors))


def _build_image_providers(settings: Any) -> List[Dict[str, str]]:
    """Load image providers from the JSON config file.

    Schema: a JSON array of objects with these fields:
      - name     str   - free-form label used in logs
      - api_url  str   - either an /images/generations endpoint, or a chat
                         endpoint that the call layer will rewrite
      - api_key  str   - Bearer token
      - models   list  - one or more model names; each becomes its own
                         provider entry, tried in array order
      - proxy    str   - optional SOCKS5/HTTP proxy applied ONLY to this
                         provider; never leaks to other network calls
      - enabled  bool  - defaults to true; set false to temporarily skip

    Entries missing api_key/api_url or with empty models are silently skipped.
    """
    raw_path = getattr(settings, "image_providers_file", "image_providers.json")
    path = Path(raw_path)
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parents[3]
        path = project_root / path

    if not path.exists():
        logger.warning("image providers file not found: %s", path)
        return []

    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("failed to parse image providers file %s: %s", path, exc)
        return []

    if not isinstance(config, list):
        logger.error("image providers file root must be a JSON array: %s", path)
        return []

    providers: List[Dict[str, str]] = []
    for entry in config:
        if not isinstance(entry, dict):
            continue
        if not entry.get("enabled", True):
            continue
        api_key = str(entry.get("api_key") or "").strip()
        api_url = str(entry.get("api_url") or "").strip()
        if not api_key or not api_url:
            continue
        models_raw = entry.get("models") or []
        if isinstance(models_raw, str):
            models = [m.strip() for m in models_raw.split(",") if m.strip()]
        else:
            models = [str(m).strip() for m in models_raw if str(m).strip()]
        proxy = str(entry.get("proxy") or "").strip()
        name = str(entry.get("name") or "").strip()
        for model in models:
            providers.append({
                "name": name,
                "api_key": api_key,
                "api_url": api_url,
                "model": model,
                "proxy": proxy,
            })

    return providers


def _redact_url(url: str) -> str:
    return url.split("?", 1)[0]


async def _generate_with_provider(
    client: httpx.AsyncClient,
    provider: Dict[str, str],
    prompt: str,
) -> bytes:
    """Call one provider. If provider declares a proxy, use a temporary client
    with that proxy applied only to this call (and the subsequent image-URL
    download); otherwise reuse the caller's proxy-less client."""
    proxy = provider.get("proxy") or ""
    if proxy:
        timeout = httpx.Timeout(180.0, connect=30.0)
        async with httpx.AsyncClient(proxy=proxy, timeout=timeout) as proxied:
            return await _do_call_provider(proxied, provider, prompt)
    return await _do_call_provider(client, provider, prompt)


async def _do_call_provider(
    client: httpx.AsyncClient,
    provider: Dict[str, str],
    prompt: str,
) -> bytes:
    api_url = provider["api_url"].rstrip("/")
    model = provider["model"]
    headers = {
        "Authorization": f"Bearer {provider['api_key']}",
        "Content-Type": "application/json",
    }

    image_api_url = api_url
    if image_api_url.endswith("/chat/completions"):
        image_api_url = image_api_url.removesuffix("/chat/completions")
    if not image_api_url.endswith("/images/generations"):
        image_api_url = f"{image_api_url}/images/generations"

    response = await client.post(
        image_api_url,
        headers=headers,
        json={"model": model, "prompt": prompt, "n": 1},
        timeout=120.0,
    )

    # Keep compatibility with gateways that only expose image models through chat.
    if response.status_code == 404 and api_url.endswith("/chat/completions"):
        chat_payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an image generation model. Generate exactly one "
                        "news-media cover image. Return the generated image as a URL, "
                        "base64 data, data URI, or JSON containing one of those fields. "
                        "Do not return ordinary prose."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        response = await client.post(api_url, headers=headers, json=chat_payload, timeout=120.0)

    _raise_for_status_with_body(response)
    data = response.json()
    try:
        return await _image_bytes_from_generation_response(client, data)
    except ValueError as generation_exc:
        try:
            return await _image_bytes_from_chat_response(client, data)
        except ValueError as chat_exc:
            raise ValueError(
                f"AI 返回中未解析到图片数据: generation={generation_exc}; chat={chat_exc}"
            ) from chat_exc


async def _generate_via_images_generation(
    client: httpx.AsyncClient,
    settings: Any,
    prompt: str,
) -> bytes:
    """Deprecated single-provider helper. Kept as a thin shim for ad-hoc
    callers that want to hit the first configured provider's
    /images/generations endpoint directly. The cover pipeline goes through
    ``_generate_via_chat_completion`` and never calls this."""
    providers = _build_image_providers(settings)
    if not providers:
        raise ValueError("图片生成 API Key 未配置")
    return await _do_call_provider(client, providers[0], prompt)


async def _image_bytes_from_generation_response(
    client: httpx.AsyncClient,
    data: Dict[str, Any],
) -> bytes:
    if not data.get("data"):
        raise ValueError("AI 返回的图片数据为空")

    item = data["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])

    image_url = item.get("url") or item.get("image_url")
    if isinstance(image_url, dict):
        image_url = image_url.get("url")
    if image_url:
        img_response = await client.get(image_url, timeout=120.0)
        _raise_for_status_with_body(img_response)
        return img_response.content

    raise ValueError("AI 返回的图片 URL/base64 为空")



async def _image_bytes_from_chat_response(
    client: httpx.AsyncClient,
    data: Dict[str, Any],
) -> bytes:
    choices = data.get("choices") or []
    candidates: List[Any] = []

    for choice in choices:
        message = choice.get("message") or {}
        candidates.extend(
            [
                message.get("content"),
                message.get("images"),
                message.get("image"),
                message.get("image_url"),
                message.get("b64_json"),
            ]
        )

    # Some gateways use vendor-specific top-level keys.
    candidates.extend(
        [
            data.get("image"),
            data.get("images"),
            data.get("image_url"),
            data.get("b64_json"),
            data.get("url"),
        ]
    )

    for candidate in candidates:
        try:
            return await _image_bytes_from_candidate(client, candidate)
        except ValueError:
            continue

    raise ValueError("AI 聊天接口返回中未找到图片 URL/base64")


async def _image_bytes_from_candidate(client: httpx.AsyncClient, candidate: Any) -> bytes:
    if not candidate:
        raise ValueError("空图片候选")

    if isinstance(candidate, list):
        for item in candidate:
            try:
                return await _image_bytes_from_candidate(client, item)
            except ValueError:
                continue
        raise ValueError("列表中未找到图片")

    if isinstance(candidate, dict):
        for key in ("b64_json", "base64", "data", "image_base64"):
            value = candidate.get(key)
            if isinstance(value, str):
                try:
                    return _decode_image_text(value)
                except ValueError:
                    pass
        for key in ("url", "image_url"):
            value = candidate.get(key)
            if isinstance(value, dict):
                value = value.get("url")
            if isinstance(value, str):
                return await _download_or_decode_image(client, value)
        raise ValueError("字典中未找到图片字段")

    if isinstance(candidate, str):
        text = candidate.strip()
        if not text:
            raise ValueError("空字符串候选")

        # JSON content returned inside choices[].message.content.
        if text.startswith("```"):
            parts = text.split("\n", 1)
            if len(parts) == 2:
                text = parts[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        import json
        import re

        if text.startswith("{") or text.startswith("["):
            try:
                return await _image_bytes_from_candidate(client, json.loads(text))
            except (json.JSONDecodeError, ValueError):
                pass

        # Markdown image or plain URL in text.
        url_match = re.search("https?://[^\\s)'\"]+", text)
        if url_match:
            return await _download_or_decode_image(client, url_match.group(0))

        data_uri_match = re.search("data:image/[^;]+;base64,[A-Za-z0-9+/=\\s]+", text)
        if data_uri_match:
            return _decode_image_text(data_uri_match.group(0))

        return _decode_image_text(text)

    raise ValueError(f"不支持的图片候选类型: {type(candidate).__name__}")


async def _download_or_decode_image(client: httpx.AsyncClient, value: str) -> bytes:
    value = value.strip()
    if value.startswith("data:image/"):
        return _decode_image_text(value)
    if value.startswith("http://") or value.startswith("https://"):
        img_response = await client.get(value, timeout=120.0)
        _raise_for_status_with_body(img_response)
        return img_response.content
    return _decode_image_text(value)


def _decode_image_text(value: str) -> bytes:
    text = value.strip()
    if text.startswith("data:image/"):
        _, text = text.split(",", 1)
    try:
        return base64.b64decode("".join(text.split()), validate=True)
    except Exception as exc:
        raise ValueError("不是有效的 base64 图片数据") from exc


def _raise_for_status_with_body(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = response.text.replace("\n", " ")[:500]
        raise httpx.HTTPStatusError(
            f"{exc}; response_body={body}",
            request=exc.request,
            response=exc.response,
        ) from exc


def _clean_content_excerpt(content: Optional[str], max_chars: int = 800) -> str:
    """提取适合放入图片生成 prompt 的正文片段。"""
    if not content:
        return ""
    text = re.sub(r"<[^>]+>", " ", content)
    text = re.sub(r"[#>*_`\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _prepare_output_path(output_path: Optional[str], *, suffix: str, prefix: str) -> Path:
    if output_path:
        return Path(output_path)
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix=prefix)
    out = Path(tmp.name)
    tmp.close()
    return out


def _crop_to_cover_ratio(img: Image.Image) -> Image.Image:
    """裁剪图片为 2.35:1 比例（900x383）。"""
    target_ratio = COVER_WIDTH / COVER_HEIGHT
    current_ratio = img.width / img.height

    if current_ratio > target_ratio:
        # 图片太宽，裁剪左右（居中）
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        # 图片太高，从顶部裁剪（保留上部内容）
        new_height = int(img.width / target_ratio)
        img = img.crop((0, 0, img.width, new_height))

    # 缩放到目标尺寸
    img = img.resize((COVER_WIDTH, COVER_HEIGHT), Image.Resampling.LANCZOS)
    return img


def _generate_text_cover(title: str, output_path: Optional[str] = None) -> str:
    """生成文字封面（兜底方案）。"""
    img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT))
    draw = ImageDraw.Draw(img)

    # 渐变背景（深蓝→深灰）
    for y in range(COVER_HEIGHT):
        ratio = y / COVER_HEIGHT
        r = int(20 + ratio * 15)
        g = int(40 + ratio * 20)
        b = int(80 + ratio * 30)
        draw.line([(0, y), (COVER_WIDTH, y)], fill=(r, g, b))

    # 装饰线条
    accent_color = (255, 200, 80)
    draw.rectangle([0, 0, 12, COVER_HEIGHT], fill=accent_color)
    draw.line([(60, 80), (840, 80)], fill=(255, 255, 255, 80), width=2)

    # 字体
    title_font = _load_font(48)
    subtitle_font = _load_font(24)
    small_font = _load_font(20)

    # 标题处理
    clean_title = title.replace("今天怎么看｜", "").replace("今天怎么看|", "")

    # 绘制品牌
    draw.text((60, 35), "今天怎么看", font=subtitle_font, fill=accent_color)

    # 绘制主标题（自动换行）
    _draw_wrapped_text(draw, clean_title, title_font, max_width=780, start_y=120, fill=(255, 255, 255))

    # 底部标识
    draw.text((60, 330), "现象观察 · 财经观察", font=small_font, fill=(200, 210, 230))

    out = _prepare_output_path(output_path, suffix=".jpg", prefix="autowz_cover_")
    img.save(str(out), "JPEG", quality=90)

    logger.info("封面图已生成: %s", out)
    return str(out)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """加载中文字体，失败则使用默认字体。"""
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
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
    lines: List[str] = []
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
