import logging

from app.services.guard.blocklist import match_high_risk, match_medium_risk
from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.guard")

SYSTEM_PROMPT = """你是一位内容风控审核专家。请对以下文章进行风险评估。

评估维度：
1. 政治敏感：是否涉及敏感政治话题、领导人评价、制度批评
2. 谣言风险：是否包含未经核实的信息或传言
3. 极端措辞：是否有煽动性、仇恨性或极端情绪化表达
4. 诱导标题：标题是否存在夸大、误导或标题党倾向
5. 法律风险：是否涉及诽谤、侵权、泄露隐私等

请以JSON格式返回评估结果：
{
  "risk_level": "low/medium/high",
  "risk_items": ["具体风险点1", "具体风险点2"],
  "suggestion": "修改建议（如果有的话）"
}
"""


class GuardService:
    """风控审核：先用集中词库（blocklist.py）快速拦截，再用 LLM 深度评估。"""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or get_llm_client()

    async def review(self, article: dict) -> dict:
        text = article.get("content_markdown", "") + " " + article.get("title", "")

        # Layer 1: 关键词快速检查（命中即拦截，不再走 LLM）
        hit_high = match_high_risk(text)
        if hit_high:
            logger.warning("关键词拦截 [high]: 命中 '%s'", hit_high)
            return {
                "risk_level": "high",
                "risk_items": [f"命中高风险关键词: {hit_high}"],
                "suggestion": f"请删除或替换包含 [{hit_high}] 的内容",
            }

        hit_medium = match_medium_risk(text)
        if hit_medium:
            logger.warning("关键词拦截 [medium]: 命中 '%s'", hit_medium)
            return {
                "risk_level": "medium",
                "risk_items": [f"命中中风险关键词: {hit_medium}"],
                "suggestion": f"建议审查包含 [{hit_medium}] 的上下文",
            }

        # Layer 2: LLM 深度审核
        try:
            result = await self.llm.json_completion(
                SYSTEM_PROMPT,
                f"标题：{article.get('title', '')}\n\n正文：\n{article.get('content_markdown', '')}",
                temperature=0.1,
                max_tokens=1000,
            )
            risk_level = result.get("risk_level", "low")
            if risk_level not in ("low", "medium", "high"):
                risk_level = "low"
            logger.info("LLM 风控审核完成: risk_level=%s", risk_level)
            return {
                "risk_level": risk_level,
                "risk_items": result.get("risk_items", []),
                "suggestion": result.get("suggestion", ""),
            }
        except Exception as exc:
            logger.error("LLM 风控审核失败，默认放行: %s", exc)
            return {"risk_level": "low", "risk_items": [], "suggestion": ""}
