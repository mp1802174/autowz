import logging

from app.services.collector.search import NewsItem
from app.services.guard.blocklist import is_topic_risky
from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.selector")

SYSTEM_PROMPT = """你是《今天怎么看》公众号的选题编辑。从今日新闻列表中选出最值得写评论的话题。

选题优先级（很重要）：
- 同等条件下，优先选择财经类、产业类、宏观经济、金融政策、资本市场、消费与就业等相关新闻。
- 其次优先选择国际元首、大国领导人、高层会晤、外交博弈、国际关系变化等相关新闻。
- 其次优先选择国际局势、地缘政治、贸易摩擦、关税、战争与停火谈判、全球供应链变化等国际形势话题。
- 对明星八卦、纯情绪热搜、猎奇事件、缺乏分析空间的碎片化社会新闻，除非重大公共价值明显，否则应降权。

评分维度（每项1-10分）：
1. 题材优先级：是否属于财经/国际元首/国际形势等优先方向
2. 社会关注度：普通读者是否关心
3. 争议度：是否存在明显的观点对立，能引发讨论
4. 评论空间：是否有足够的分析角度，不是纯事实报道
5. 安全性：发表评论的风险程度（10分=非常安全，涉政涉军的给低分）
6. 调性匹配：是否适合"理性评论、敢说真话"的定位

请优先挑选“有分析价值且属于优先题材”的新闻，而不是只看热度。
请以JSON格式返回，示例：
{
  "rankings": [
    {
      "index": 0,
      "total_score": 42,
      "reason": "一句话说明为什么选这个话题"
    }
  ]
}

只返回总分排名前6的话题。按 total_score 从高到低排列。
"""

CATEGORY_PROMPTS = {
    "finance": SYSTEM_PROMPT,
    "entertainment": """你是《今天怎么看》公众号的选题编辑。从今日新闻列表中选出最适合写娱乐评论的话题。

选题优先级（很重要）：
- 优先选择娱乐、文化、生活方式、明星、综艺、电影、音乐、游戏、体育、旅游、美食、时尚、消费潮流、社会趣闻等相关新闻。
- 其次优先选择热门社会话题、轻松有话题性的民生新闻。
- 对严肃财经、国际政治、军事等话题应降权，除非有明显的娱乐/生活视角。

评分维度（每项1-10分）：
1. 娱乐性：是否有趣、有话题性
2. 社会关注度：普通读者是否关心
3. 争议度：是否存在明显的观点对立，能引发讨论
4. 评论空间：是否有足够的分析角度
5. 安全性：发表评论的风险程度（10分=非常安全）
6. 调性匹配：是否适合"理性评论、敢说真话"的定位

请优先挑选"有趣且有分析价值"的新闻。
请以JSON格式返回，示例：
{
  "rankings": [
    {"index": 0, "total_score": 42, "reason": "一句话说明为什么选这个话题"}
  ]
}
只返回总分排名前6的话题。按 total_score 从高到低排列。""",
    "international": """你是《今天怎么看》公众号的选题编辑。从今日新闻列表中选出最适合写国际形势评论的话题。

选题优先级（很重要）：
- 优先选择国际关系、地缘政治、大国博弈、外交动态、贸易摩擦、关税、制裁、战争与停火、全球供应链等相关新闻。
- 其次优先选择国际元首、高层会晤、峰会、联合国、北约、欧盟等国际组织动态。
- 对国内财经、娱乐八卦等话题应降权，除非有明显的国际联动视角。

评分维度（每项1-10分）：
1. 题材优先级：是否属于国际形势/地缘政治优先方向
2. 社会关注度：中国读者是否关心此事
3. 争议度：是否存在明显的观点对立，能引发讨论
4. 评论空间：是否有足够的分析角度
5. 安全性：发表评论的风险程度（10分=非常安全，涉华敏感给低分）
6. 调性匹配：是否适合"理性评论、敢说真话"的定位

请优先挑选"有深度分析价值且属于国际形势题材"的新闻。
请以JSON格式返回，示例：
{
  "rankings": [
    {"index": 0, "total_score": 42, "reason": "一句话说明为什么选这个话题"}
  ]
}
只返回总分排名前6的话题。按 total_score 从高到低排列。""",
}

PRIORITY_KEYWORDS = {
    "finance": [
        "财经", "经济", "金融", "股市", "a股", "港股", "美股", "基金", "债券", "汇率", "人民币", "美元",
        "利率", "降息", "加息", "通胀", "cpi", "ppi", "gdp", "就业", "消费", "楼市", "房价", "房地产",
        "车企", "产业", "出口", "外贸", "关税", "贸易", "供应链", "平台经济", "民营经济", "财政", "税收",
    ],
    "leaders": [
        "总统", "总理", "主席", "首相", "国王", "王储", "元首", "领导人", "会晤", "峰会", "访华", "访美",
        "访问", "内阁", "白宫", "克里姆林宫", "唐宁街", "欧盟", "北约", "联合国",
    ],
    "international": [
        "国际", "局势", "形势", "外交", "地缘", "冲突", "停火", "谈判", "制裁", "军援", "俄乌", "中东",
        "巴以", "伊朗", "以色列", "乌克兰", "俄罗斯", "叙利亚", "朝鲜半岛", "南海", "台海", "印太", "全球",
        "多边", "盟友", "博弈", "关税", "贸易战",
    ],
}

DOWNRANK_KEYWORDS = [
    "明星", "恋情", "离婚", "绯闻", "八卦", "塌房", "网红", "热舞", "穿搭", "颜值", "综艺", "演唱会", "粉丝",
    "搞笑", "猎奇", "奇葩", "震惊", "曝光", "吃瓜",
]


class TopicSelectorService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or get_llm_client()

    async def select(
        self, news_items: list[NewsItem], *, short_count: int = 2, long_count: int = 0,
        category: str | None = None,
    ) -> dict[str, list[NewsItem]]:
        """从新闻列表中选出适合评论的优先话题。"""
        if not news_items:
            return {"short": [], "long": []}

        # 前置硬拦截：剔除涉政体/涉港澳台/涉军/涉民族/涉群体事件/涉中美博弈
        # 等高/中风险题材，自动管线一律不生成
        before = len(news_items)
        filtered: list[NewsItem] = []
        for n in news_items:
            risky, level, hit = is_topic_risky(f"{n.title} {n.description or ''}")
            if risky:
                logger.info("选题硬拦截 [%s/%s]: %s", level, hit, n.title)
                continue
            filtered.append(n)
        news_items = filtered
        if before != len(news_items):
            logger.info("blocklist 过滤: %d → %d", before, len(news_items))

        if not news_items:
            logger.warning("blocklist 过滤后无可用新闻")
            return {"short": [], "long": []}

        prompt = CATEGORY_PROMPTS.get(category, SYSTEM_PROMPT)
        # 构建新闻列表供 LLM 评分
        topic_list = "\n".join(
            f"{i}. [{n.source}] {n.title}"
            + (f" — {n.description[:80]}" if n.description else "")
            for i, n in enumerate(news_items[:30])
        )

        try:
            result = await self.llm.json_completion(
                prompt,
                f"今日新闻列表：\n{topic_list}",
                temperature=0.3,
                max_tokens=2000,
            )
            rankings = result.get("rankings", [])
            rankings.sort(key=lambda r: r.get("total_score", 0), reverse=True)

            selected_topics: list[NewsItem] = []
            target_count = short_count + long_count

            for r in rankings:
                idx = r.get("index", -1)
                if idx < 0 or idx >= len(news_items):
                    continue
                item = news_items[idx]
                if item in selected_topics:
                    continue
                selected_topics.append(item)
                if len(selected_topics) >= target_count:
                    break

            if len(selected_topics) < target_count:
                logger.warning("LLM 选题数量不足，使用 fallback 补足: selected=%d target=%d", len(selected_topics), target_count)
                fallback = self._fallback_select(news_items, short_count, long_count)
                for item in fallback["short"] + fallback["long"]:
                    if item not in selected_topics:
                        selected_topics.append(item)
                    if len(selected_topics) >= target_count:
                        break

            logger.info("LLM 选题完成: selected=%d", len(selected_topics))
            return {"short": selected_topics[:target_count], "long": []}

        except Exception as exc:
            logger.error("LLM 选题失败，回退到关键词优先模式: %s", exc)
            return self._fallback_select(news_items, short_count, long_count)

    @classmethod
    def _priority_score(cls, item: NewsItem) -> tuple[int, int]:
        text = f"{item.title} {item.description}".lower()
        score = 0

        if any(k in text for k in PRIORITY_KEYWORDS["finance"]):
            score += 30
        if any(k in text for k in PRIORITY_KEYWORDS["leaders"]):
            score += 20
        if any(k in text for k in PRIORITY_KEYWORDS["international"]):
            score += 15
        if any(k in text for k in DOWNRANK_KEYWORDS):
            score -= 25

        return score, -len(item.title)

    @classmethod
    def _fallback_select(
        cls, news_items: list[NewsItem], short_count: int, long_count: int,
    ) -> dict[str, list[NewsItem]]:
        """LLM 不可用时的兜底选题：按关键词优先级排序后取前 N 条。"""
        ranked = sorted(
            news_items,
            key=lambda item: cls._priority_score(item),
            reverse=True,
        )
        total = short_count + long_count
        return {
            "short": ranked[:short_count],
            "long": ranked[short_count: short_count + long_count] if long_count > 0 else ranked[short_count:total],
        }
