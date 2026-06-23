import pytest

from app.modules.finance.module import FinanceModule
from app.services.collector.search import NewsItem
from app.services.content_length import count_cn_chars, trim_markdown_to_max_chars
from app.services.quality import check_quality


def _unique_cn_text(length: int) -> str:
    chars = [chr(0x4E00 + i) for i in range(length)]
    sentences = ["".join(chars[i:i + 35]) + "。" for i in range(0, length, 35)]
    return "\n\n".join("".join(sentences[i:i + 4]) for i in range(0, len(sentences), 4))


def test_quality_checker_blocks_degenerated_long_sentence():
    content = "开头说明。\n\n" + "退化长句" * 180

    result = check_quality("测试标题", content, min_chars=600, max_chars=800)

    assert not result.passed
    assert any("退化超长句" in r for r in result.reasons)


def test_quality_checker_allows_complete_structured_text():
    content = _unique_cn_text(650)

    result = check_quality("正常标题", content, min_chars=600, max_chars=800)

    assert result.passed
    assert result.score >= 80
    assert result.reasons == []


def test_trim_does_not_fake_sentence_ending_after_hard_cut():
    text = "这是一个完整句。" + "后面这段没有自然句末" * 80

    trimmed = trim_markdown_to_max_chars(text, max_chars=40)

    assert count_cn_chars(trimmed) <= 40
    assert trimmed == "这是一个完整句。"


@pytest.mark.asyncio
async def test_quality_gate_regenerates_once_then_rejects():
    module = FinanceModule()
    module.writer.min_chars = 600
    module.writer.max_chars = 800

    bad = {
        "title": "坏稿",
        "digest": "摘要",
        "content_markdown": "坏稿内容" * 20,
        "content_html": "<p>坏稿内容</p>",
        "style_score": 85,
    }
    calls = 0

    async def fake_generate(_: NewsItem):
        nonlocal calls
        calls += 1
        return dict(bad)

    module.generate_article = fake_generate  # type: ignore[method-assign]

    draft, quality = await module._generate_quality_checked_article(
        NewsItem(title="测试话题", source="manual", description="")
    )

    assert calls == 2
    assert draft["style_score"] == quality.score
    assert not quality.passed
