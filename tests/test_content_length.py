from app.services.content_length import MAX_ARTICLE_CHARS, append_char_count_suffix, count_cn_chars, finalize_article, trim_markdown_to_max_chars


def test_trim_markdown_to_max_chars_keeps_limit():
    text = "\n\n".join([
        "第一段" + "甲" * 120,
        "第二段" + "乙" * 120,
        "第三段" + "丙" * 120,
    ])

    trimmed = trim_markdown_to_max_chars(text)

    assert count_cn_chars(trimmed) <= MAX_ARTICLE_CHARS


def test_trim_markdown_to_max_chars_keeps_short_text():
    text = "这是一个两百字以内的短文。"
    assert trim_markdown_to_max_chars(text) == text


def test_append_char_count_suffix_marks_body_count():
    text = "甲乙丙丁。"
    assert append_char_count_suffix(text) == "甲乙丙丁。\n\n（全文共4字）"


def test_finalize_article_keeps_total_within_limit_and_appends_suffix():
    text = "甲" * 400
    final = finalize_article(text)
    assert final.endswith("）")
    assert "（全文共" in final
    assert count_cn_chars(final) <= MAX_ARTICLE_CHARS
