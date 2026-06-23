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
        article = {"content_markdown": "中美市场出现波动", "title": "标题"}
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

    @pytest.mark.asyncio
    async def test_semantic_quality_low_blocks_as_high_risk(self):
        guard = GuardService()
        guard.llm = AsyncMock()
        guard.llm.json_completion = AsyncMock(return_value={
            "risk_level": "low",
            "risk_items": [],
            "suggestion": "",
            "quality_score": 55,
            "quality_items": ["信息增量不足"],
        })
        article = {
            "title": "测试标题",
            "content_markdown": "这是测试内容。" * 80,
            "style_score": 90,
            "min_chars": 1,
            "max_chars": 1000,
        }

        result = await guard.review(article)

        assert result["risk_level"] == "high"
        assert any("内容质量过低" in item for item in result["risk_items"])

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_rule_quality(self):
        guard = GuardService()
        guard.llm = AsyncMock()
        guard.llm.json_completion = AsyncMock(side_effect=RuntimeError("LLM down"))
        article = {
            "title": "测试标题",
            "content_markdown": "短文。",
            "style_score": 40,
        }

        result = await guard.review(article)

        assert result["risk_level"] == "high"
        assert result["quality_score"] < 80
        assert result["quality_items"]
