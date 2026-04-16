"""新闻素材采集：为 LLM 写作提供新闻事实依据。

两种用途：
1. fetch_news_pool() — 获取今日新闻列表，供 LLM 选题
2. fetch_topic_detail() — 对选中的话题，搜索详细报道作为写作素材
"""

import logging
import re
from dataclasses import dataclass, field

import feedparser
import httpx

from app.core.config import get_settings

logger = logging.getLogger("autowz.collector.search")


@dataclass
class NewsItem:
    """新闻条目（用于选题池）。"""
    title: str
    source: str = ""
    description: str = ""
    url: str = ""
    time: str = ""


@dataclass
class SearchResult:
    """详细搜索结果（用于写作素材）。"""
    title: str
    snippet: str
    source: str = ""
    url: str = ""


@dataclass
class TopicContext:
    """话题的新闻素材上下文，喂给 LLM 写作。"""
    topic: str
    results: list[SearchResult] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        if not self.results:
            return ""
        lines = [
            "以下是关于该话题的最新真实新闻报道（请严格基于这些事实撰写，不要编造细节）：",
            "",
        ]
        for i, r in enumerate(self.results, 1):
            source_tag = f"（来源：{r.source}）" if r.source else ""
            lines.append(f"{i}. {r.title}{source_tag}")
            if r.snippet:
                lines.append(f"   {r.snippet}")
            lines.append("")
        return "\n".join(lines)


# ──────────── 天行API频道配置 ────────────

TIANAPI_CHANNELS = [
    ("国内新闻", "guonei"),
    ("财经新闻", "caijing"),
    ("社会新闻", "social"),
]

# ──────────── RSS 新闻源 ────────────

RSS_SOURCES = [
    ("新华社", "https://plink.anyfeeder.com/newscn/whxw"),
    ("人民网", "http://www.people.com.cn/rss/politics.xml"),
]


class NewsCollector:
    """新闻采集器：天行API + RSS + 搜狗新闻搜索。"""

    TIANAPI_BASE = "https://apis.tianapi.com"
    SOGOU_NEWS_URL = "https://news.sogou.com/news"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    def __init__(self) -> None:
        self.tianapi_key = get_settings().tianapi_key

    # ━━━━━━━━━━ 1. 获取今日新闻池（供 LLM 选题）━━━━━━━━━━

    async def fetch_news_pool(self, per_channel: int = 10) -> list[NewsItem]:
        """从天行API + RSS 获取今日新闻列表，供 LLM 选题。"""
        all_news: list[NewsItem] = []

        # 天行API
        if self.tianapi_key:
            for name, endpoint in TIANAPI_CHANNELS:
                items = await self._fetch_tianapi(endpoint, per_channel)
                all_news.extend(items)
                logger.info("天行API [%s]: %d 条", name, len(items))
        else:
            logger.warning("TIANAPI_KEY 未配置，跳过天行API")

        # RSS 补充
        for name, url in RSS_SOURCES:
            items = await self._fetch_rss(name, url, per_channel)
            all_news.extend(items)
            logger.info("RSS [%s]: %d 条", name, len(items))

        # 按标题去重
        seen: set[str] = set()
        deduped: list[NewsItem] = []
        for item in all_news:
            key = item.title[:15]
            if key not in seen:
                seen.add(key)
                deduped.append(item)

        logger.info("新闻池采集完成: 原始 %d → 去重 %d", len(all_news), len(deduped))
        return deduped

    async def _fetch_tianapi(self, endpoint: str, num: int) -> list[NewsItem]:
        """从天行API获取新闻列表。"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.TIANAPI_BASE}/{endpoint}/index",
                    params={"key": self.tianapi_key, "num": str(num)},
                )
                data = resp.json()
                if data.get("code") != 200:
                    logger.warning("天行API [%s] 返回 code=%s", endpoint, data.get("code"))
                    return []
                items = []
                for n in data.get("result", {}).get("newslist", []):
                    items.append(NewsItem(
                        title=n.get("title", ""),
                        source=n.get("source", ""),
                        description=n.get("description", ""),
                        url=n.get("url", ""),
                        time=n.get("ctime", ""),
                    ))
                return items
        except Exception as exc:
            logger.warning("天行API [%s] 请求失败: %s", endpoint, exc)
            return []

    async def _fetch_rss(self, name: str, url: str, limit: int) -> list[NewsItem]:
        """从 RSS 获取新闻列表。"""
        try:
            feed = feedparser.parse(url)
            items = []
            for entry in feed.entries[:limit]:
                title = entry.get("title", "")
                summary_html = entry.get("summary", "") or entry.get("description", "")
                description = re.sub(r'<[^>]+>', '', summary_html).strip()[:300]
                items.append(NewsItem(
                    title=title,
                    source=name,
                    description=description,
                    url=entry.get("link", ""),
                    time=entry.get("published", ""),
                ))
            return items
        except Exception as exc:
            logger.warning("RSS [%s] 获取失败: %s", name, exc)
            return []

    # ━━━━━━━━━━ 2. 获取话题详细报道（供 LLM 写作）━━━━━━━━━━

    async def fetch_topic_detail(self, topic: str, max_results: int = 8) -> TopicContext:
        """用搜狗新闻搜索话题的详细报道，作为 LLM 写作素材。"""
        context = TopicContext(topic=topic)
        results = await self._search_sogou_news(topic, max_results)
        context.results = results[:max_results]
        logger.info("话题素材采集 [%s]: %d 条", topic, len(context.results))
        return context

    async def _search_sogou_news(self, query: str, max_results: int) -> list[SearchResult]:
        """搜狗新闻搜索，按时间排序。"""
        try:
            async with httpx.AsyncClient(
                timeout=15, headers=self.HEADERS, follow_redirects=True,
            ) as client:
                resp = await client.get(
                    self.SOGOU_NEWS_URL,
                    params={"query": query, "sort": "1"},
                )
                resp.raise_for_status()
                return self._parse_sogou_html(resp.text, max_results)
        except Exception as exc:
            logger.warning("搜狗新闻搜索失败: %s", exc)
            return []

    @staticmethod
    def _parse_sogou_html(html: str, max_results: int) -> list[SearchResult]:
        """解析搜狗新闻搜索结果。"""
        results: list[SearchResult] = []
        parts = re.split(r'(?=<h3[^>]*>)', html)

        for part in parts:
            if len(results) >= max_results:
                break
            tm = re.search(r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>', part, re.DOTALL)
            if not tm:
                continue
            title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()
            if len(title) < 8:
                continue

            # 摘要：找最长的 <p> 文本
            snippet = ""
            for pm in re.finditer(r'<p[^>]*>(.*?)</p>', part, re.DOTALL):
                clean = re.sub(r'<[^>]+>', '', pm.group(1)).strip()
                if len(clean) > len(snippet):
                    snippet = clean

            # 来源
            source = ""
            for sm in re.finditer(r'<span[^>]*>(.*?)</span>', part, re.DOTALL):
                text = re.sub(r'<[^>]+>', '', sm.group(1)).strip()
                if not text or len(text) > 20 or "推荐" in text or "搜索" in text:
                    continue
                if re.search(r'[\u4e00-\u9fff]', text):
                    source = text
                    break

            if title and (snippet or source):
                results.append(SearchResult(
                    title=title, snippet=snippet, source=source,
                ))

        return results
