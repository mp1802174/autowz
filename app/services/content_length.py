import re

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

    chars: list[str] = []
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


def append_char_count_suffix(text: str) -> str:
    body = _strip_count_suffix(text)
    if not body:
        return body
    char_count = count_cn_chars(body)
    return f"{body}\n\n（全文共{char_count}字）"


def finalize_article(text: str, max_chars: int = MAX_ARTICLE_CHARS) -> str:
    """先按上限裁剪正文，再在结尾追加字数括号。总字数包含括号时仍不超过上限。"""
    suffix_template = "（全文共999字）"
    body_limit = max(0, max_chars - count_cn_chars(suffix_template))
    body = trim_markdown_to_max_chars(_strip_count_suffix(text), body_limit)
    return append_char_count_suffix(body)
