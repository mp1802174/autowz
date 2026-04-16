import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.schemas import ArticlePreviewRequest
from app.services.pipeline import ArticlePipeline


@pytest.mark.asyncio
async def test_preview_generates_article():
    pipeline = ArticlePipeline()

    # mock 所有 LLM 调用
    mock_draft = {
        "title": "今天怎么看｜测试话题",
        "digest": "测试摘要",
        "content_markdown": "测试内容正文",
        "content_html": "<p>测试内容正文</p>",
        "style_score": 85,
    }
    pipeline.writer.generate = AsyncMock(return_value=mock_draft)
    pipeline.humanizer.rewrite = AsyncMock(return_value={
        **mock_draft,
        "style_score": 90,
    })
    pipeline.guard.review = AsyncMock(return_value={
        "risk_level": "low",
        "risk_items": [],
        "suggestion": "",
    })

    request = ArticlePreviewRequest(topic="测试话题", article_type="short")
    result = await pipeline.generate_preview(request)

    assert result.title == "今天怎么看｜测试话题"
    assert result.risk_level == "low"
    assert result.style_score == 90
    pipeline.writer.generate.assert_called_once()
