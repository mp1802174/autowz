import pytest
from unittest.mock import AsyncMock

from app.models.schemas import ArticlePreviewRequest
from app.services.pipeline import ArticlePipeline


@pytest.mark.asyncio
async def test_preview_generates_article():
    pipeline = ArticlePipeline("finance")

    mock_draft = {
        "title": "测试话题",
        "digest": "测试摘要",
        "content_markdown": "测试内容正文",
        "content_html": "<p>测试内容正文</p>",
        "style_score": 85,
    }
    pipeline.module.generate_article = AsyncMock(return_value=mock_draft)
    pipeline.guard.review = AsyncMock(return_value={
        "risk_level": "low",
        "risk_items": [],
        "suggestion": "",
    })

    request = ArticlePreviewRequest(topic="测试话题")
    result = await pipeline.generate_preview(request)

    assert result.title == "测试话题"
    assert result.risk_level == "low"
    assert result.style_score == 85
    pipeline.module.generate_article.assert_called_once()
