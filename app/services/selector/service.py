import logging

from app.services.collector.search import NewsItem
from app.services.guard.blocklist import is_topic_risky
from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.selector")

SYSTEM_PROMPT = """你是《现象观察》公众号的选题编辑。从今日新闻列表中选出最值得写评论的话题。

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
    "entertainment": """你是《现象观察》公众号的选题编辑。从今日新闻列表中选出最适合写娱乐评论的话题。

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
    "livelihood": """你是《现象观察》公众号的选题编辑。从今日新闻列表中选出最适合写民生评论的话题。

选题优先级（很重要）：
- 优先选择衣食住行、医保社保、教育、就业、养老、生育、租房、物价、菜价、油价、出行、外卖、网约车、社区便民、办事服务、公共安全、环境治理、防灾减灾等贴近普通人日常的新闻。
- 其次优先选择反映普通劳动者、农民工、骑手、个体户、宝妈、银发族、年轻人焦虑等社会群体处境的新闻。
- 对娱乐八卦、严肃国际政治军事、宏观财经数据（无民生触点）等话题应降权，除非有明显的民生切入视角。

评分维度（每项1-10分）：
1. 民生贴近度：是否与普通人日常生活直接相关
2. 社会关注度：广大读者是否关心此事
3. 争议度：是否存在明显的观点对立，能引发讨论
4. 评论空间：是否有足够的分析角度
5. 安全性：发表评论的风险程度（10分=非常安全，涉群体事件/涉政体给低分）
6. 调性匹配：是否适合"理性评论、敢说真话"的定位

请优先挑选"贴近普通人且有讨论价值"的民生新闻。
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
    "livelihood": [
        "民生", "就业", "失业", "招聘", "工资", "薪资", "社保", "医保", "养老", "退休", "生育", "育儿",
        "托育", "教育", "学区", "高考", "中考", "学费", "学校", "教师", "课后",
        "医疗", "医院", "看病", "门诊", "药价", "药品",
        "住房", "租房", "房租", "公积金", "保障房", "拆迁", "回迁",
        "出行", "通勤", "地铁", "公交", "高铁", "网约车", "外卖", "骑手", "快递",
        "菜价", "肉价", "油价", "电价", "水价", "燃气", "物价", "消费", "退款", "维权", "诈骗", "电诈",
        "社区", "便民", "办事", "户籍", "户口", "落户",
        "环境", "污染", "雾霾", "垃圾",
        "事故", "火灾", "食品安全", "假冒",
        "暴雨", "台风", "暴雪", "高温", "寒潮",
        "农民工", "灵活就业", "零工", "个体户",
    ],
}

DOWNRANK_KEYWORDS = [
    "明星", "恋情", "离婚", "绯闻", "八卦", "塌房", "网红", "热舞", "穿搭", "颜值", "综艺", "演唱会", "粉丝",
    "搞笑", "猎奇", "奇葩", "震惊", "曝光", "吃瓜",
]

# OPTIMIZE: 黑名单硬过滤
BLACKLIST_KEYWORDS = [
    "娱乐", "明星", "八卦", "绯闻", "恋情", "离婚", "网红", "综艺",
    "体育", "足球", "篮球", "nba", "比赛", "球员",
    "游戏", "电竞", "主播",
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
            score += 60  # OPTIMIZE: 财经权重60分
        if any(k in text for k in PRIORITY_KEYWORDS["leaders"]):
            score += 20
        if any(k in text for k in PRIORITY_KEYWORDS["livelihood"]):
            score += 15
        if any(k in text for k in DOWNRANK_KEYWORDS):
            score -= 25

        return score, -len(item.title)

    @classmethod
    def _fallback_select(
        cls, news_items: list[NewsItem], short_count: int, long_count: int,
    ) -> dict[str, list[NewsItem]]:
        """LLM 不可用时的兜底选题：按关键词优先级排序后取前 N 条。"""
        # OPTIMIZE: 黑名单过滤
        filtered = []
        for item in news_items:
            text = f"{item.title} {item.description or ''}".lower()
            if any(k in text for k in BLACKLIST_KEYWORDS):
                continue
            filtered.append(item)

        ranked = sorted(
            filtered,
            key=lambda item: cls._priority_score(item),
            reverse=True,
        )
        total = short_count + long_count
        return {
            "short": ranked[:short_count],
            "long": ranked[short_count: short_count + long_count] if long_count > 0 else ranked[short_count:total],
        }
