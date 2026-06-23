import re
from typing import List

# OPTIMIZE: 字数控制收紧到600-800，质量闸负责判废。
MIN_ARTICLE_CHARS = 600
MAX_ARTICLE_CHARS = 800


def count_cn_chars(text: str) -> int:
    return sum(1 for c in text if "\u4e00" <= c <= "\u9fff")


SENTENCE_ENDINGS = "。！？!?…"
CLOSING_CHARS = "”』」)）\"'"


def _prefix_with_cn_limit(text: str, max_chars: int) -> str:
    """返回不超过 max_chars 个中文字符的前缀；不负责补标点。"""
    chars: List[str] = []
    cn_count = 0
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            cn_count += 1
            if cn_count > max_chars:
                break
        chars.append(ch)
    return "".join(chars)


def _trim_to_complete_sentence(text: str, max_chars: int) -> str:
    """裁到 max_chars 内最后一个完整句末，避免硬切后补句号伪装完整。"""
    prefix = _prefix_with_cn_limit(text, max_chars).rstrip()
    if not prefix:
        return ""

    last_end = -1
    for i, ch in enumerate(prefix):
        if ch in SENTENCE_ENDINGS:
            last_end = i

    if last_end < 0:
        return ""

    end = last_end + 1
    while end < len(prefix) and prefix[end] in CLOSING_CHARS:
        end += 1
    return prefix[:end].rstrip()


def trim_markdown_to_max_chars(text: str, max_chars: int = MAX_ARTICLE_CHARS) -> str:
    """将正文裁剪到指定中文字符数以内，优先保留完整段落/完整句。

    关键原则：不能字符级硬切后补句号。裁剪只能落在原文已有句末标点；
    如果裁后过短，由质量校验判废并触发重生成/弃稿。
    """
    text = (text or "").strip()
    if not text:
        return text

    if count_cn_chars(text) <= max_chars:
        return text

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]

    kept: List[str] = []
    for paragraph in paragraphs:
        candidate = "\n\n".join(kept + [paragraph]).strip()
        if count_cn_chars(candidate) <= max_chars:
            kept.append(paragraph)
            continue

        used = count_cn_chars("\n\n".join(kept))
        remaining = max_chars - used
        if remaining > 0:
            partial = _trim_to_complete_sentence(paragraph, remaining)
            if partial:
                kept.append(partial)
        break

    result = "\n\n".join(kept).strip()
    if result:
        return result

    return _trim_to_complete_sentence(text, max_chars)


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
