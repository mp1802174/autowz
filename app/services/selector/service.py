import logging

from app.services.collector.search import NewsItem
from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.selector")

SYSTEM_PROMPT = """你是《今天怎么看》公众号的选题编辑。从今日新闻列表中选出最值得写评论的话题。

评分维度（每项1-10分）：
1. 社会关注度：普通读者是否关心
2. 争议度：是否存在明显的观点对立，能引发讨论
3. 评论空间：是否有足够的分析角度，不是纯事实报道
4. 安全性：发表评论的风险程度（10分=非常安全，涉政涉军的给低分）
5. 调性匹配：是否适合"理性评论、敢说真话"的定位

同时判断每个话题更适合写成"short"（冲突型短评600-800字）还是"long"（融合分析型长文800-1200字）。

请以JSON格式返回，示例：
{
  "rankings": [
    {
      "index": 0,
      "total_score": 42,
      "article_type": "short",
      "reason": "一句话说明为什么选这个话题"
    }
  ]
}

只返回总分排名前6的话题。按 total_score 从高到低排列。
"""


class TopicSelectorService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or get_llm_client()

    async def select(
        self, news_items: list[NewsItem], *, short_count: int = 2, long_count: int = 1,
    ) -> dict[str, list[NewsItem]]:
        """从新闻列表中选出适合写短文和长文的话题。"""
        if not news_items:
            return {"short": [], "long": []}

        # 构建新闻列表供 LLM 评分
        topic_list = "\n".join(
            f"{i}. [{n.source}] {n.title}"
            + (f" — {n.description[:80]}" if n.description else "")
            for i, n in enumerate(news_items[:30])
        )

        try:
            result = await self.llm.json_completion(
                SYSTEM_PROMPT,
                f"今日新闻列表：\n{topic_list}",
                temperature=0.3,
                max_tokens=2000,
            )
            rankings = result.get("rankings", [])
            rankings.sort(key=lambda r: r.get("total_score", 0), reverse=True)

            short_topics: list[NewsItem] = []
            long_topics: list[NewsItem] = []

            for r in rankings:
                idx = r.get("index", -1)
                if idx < 0 or idx >= len(news_items):
                    continue
                item = news_items[idx]
                atype = r.get("article_type", "short")
                if atype == "long" and len(long_topics) < long_count:
                    long_topics.append(item)
                elif len(short_topics) < short_count:
                    short_topics.append(item)

                if len(short_topics) >= short_count and len(long_topics) >= long_count:
                    break

            logger.info("LLM 选题完成: short=%d, long=%d", len(short_topics), len(long_topics))
            return {"short": short_topics, "long": long_topics}

        except Exception as exc:
            logger.error("LLM 选题失败，回退到前N条: %s", exc)
            return self._fallback_select(news_items, short_count, long_count)

    @staticmethod
    def _fallback_select(
        news_items: list[NewsItem], short_count: int, long_count: int,
    ) -> dict[str, list[NewsItem]]:
        """LLM 不可用时的兜底选题：取前 N 条。"""
        return {
            "short": news_items[:short_count],
            "long": news_items[short_count: short_count + long_count],
        }
