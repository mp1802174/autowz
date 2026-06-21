import re
from typing import List

# OPTIMIZE: 字数从200-300提升到650-750
MIN_ARTICLE_CHARS = 650
MAX_ARTICLE_CHARS = 750


def count_cn_chars(text: str) -> int:
    return sum(1 for c in text if "\u4e00" <= c <= "\u9fff")


def trim_markdown_to_max_chars(text: str, max_chars: int = MAX_ARTICLE_CHARS) -> str:
    """将正文裁剪到指定中文字符数以内，优先保留段落结构。"""
    text = (text or "").strip()
    if not text:
        return text

    if count_cn_chars(text) <= max_chars:
        return text

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]

    if len(paragraphs) > 1:
        ending = paragraphs[-1]
        body = paragraphs[:-1]
        while body:
            candidate = "\n\n".join(body + [ending]).strip()
            if count_cn_chars(candidate) <= max_chars:
                return candidate
            body.pop(-1)

    chars: List[str] = []
    cn_count = 0
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            cn_count += 1
            if cn_count > max_chars:
                break
        chars.append(ch)

    trimmed = "".join(chars).rstrip("，、；：,.!?！？ \n")
    if trimmed and trimmed[-1] not in "。！？!?\n":
        trimmed += "。"
    return trimmed


def _strip_count_suffix(text: str) -> str:
    return re.sub(r"\n*（全文共\d+字）\s*$", "", (text or "").strip())


def soften_reporting_tone(text: str) -> str:
    """弱化“据X报道 / X网报道 / 消息称”等转载稿口吻。

    保留“有公开来源”的含义，但避免文章开头和正文显得像原稿转发。
    """
    body = (text or "").strip()
    if not body:
        return body

    replacements = [
        # 句首/段首常见报道腔
        (r"(^|\n)(?:据|根据)[^，。\n]{1,30}(?:消息称|报道|消息|披露|显示|统计)[，,]?", r"\1公开信息显示，"),
        (r"(^|\n)[^，。\n]{1,24}(?:网|新闻|日报|时报|周刊|客户端|媒体|记者)(?:报道|消息称|披露)[，,]?", r"\1公开信息显示，"),
        (r"(^|\n)(?:报道称|消息称|有消息称)[，,]?", r"\1公开信息显示，"),
        # 句中转述口吻
        (r"(?:据|根据)[^，。\n]{1,30}(?:消息称|报道|消息|披露)[，,]?", "公开信息显示，"),
        (r"[^，。\n]{1,24}(?:网|新闻|日报|时报|周刊|客户端|媒体|记者)(?:报道|消息称|披露)[，,]?", "公开信息显示，"),
    ]
    for pattern, repl in replacements:
        body = re.sub(pattern, repl, body)

    # 避免替换后出现重复口头禅。
    body = re.sub(r"公开信息显示，公开信息显示，", "公开信息显示，", body)
    body = re.sub(r"公开信息显示，\s*公开信息显示，", "公开信息显示，", body)
    return body.strip()


def append_char_count_suffix(text: str) -> str:
    body = _strip_count_suffix(text)
    if not body:
        return body
    char_count = count_cn_chars(body)
    return f"{body}\n\n（全文共{char_count}字）"


def finalize_article(text: str, max_chars: int = MAX_ARTICLE_CHARS) -> str:
    """裁剪正文到上限字数。

    Phase 1 改动: 去除"(全文共X字)"机器指纹,只做裁剪。
    """
    body = _strip_count_suffix(text)
    body = soften_reporting_tone(body)
    return trim_markdown_to_max_chars(body, max_chars)
