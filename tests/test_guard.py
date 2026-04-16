import pytest
from unittest.mock import AsyncMock, patch

from app.services.guard.service import GuardService


class TestGuardKeywords:
    @pytest.mark.asyncio
    async def test_high_risk_keyword(self):
        guard = GuardService()
        article = {"content_markdown": "这是一个造谣的内容", "title": "标题"}
        result = await guard.review(article)
        assert result["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_medium_risk_keyword(self):
        guard = GuardService()
        article = {"content_markdown": "必须封杀这个行为", "title": "标题"}
        result = await guard.review(article)
        assert result["risk_level"] == "medium"

    @pytest.mark.asyncio
    async def test_safe_content(self):
        guard = GuardService()
        # mock LLM 返回 low risk
        guard.llm = AsyncMock()
        guard.llm.json_completion = AsyncMock(return_value={
            "risk_level": "low",
            "risk_items": [],
            "suggestion": "",
        })
        article = {"content_markdown": "今天天气真好", "title": "日常"}
        result = await guard.review(article)
        assert result["risk_level"] == "low"
