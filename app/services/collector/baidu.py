import logging

import httpx

from app.services.collector.base import BaseCollector, CollectedTopic

logger = logging.getLogger("autowz.collector.baidu")


class BaiduCollector(BaseCollector):
    """百度热搜采集器。"""

    URL = "https://top.baidu.com/api/board?platform=wise&tab=realtime"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept": "application/json, text/plain, */*",
    }

    async def collect(self) -> list[CollectedTopic]:
        try:
            async with httpx.AsyncClient(timeout=15, headers=self.HEADERS) as client:
                resp = await client.get(self.URL)
                resp.raise_for_status()
                data = resp.json()

            cards = data.get("data", {}).get("cards", [])
            topics: list[CollectedTopic] = []
            for card in cards:
                # 百度 API 结构：cards[].content[] 每个元素内部还有一层 content[]
                outer_items = card.get("content", [])
                items: list[dict] = []
                for outer in outer_items:
                    if isinstance(outer, dict) and "content" in outer:
                        items.extend(outer["content"])
                    elif isinstance(outer, dict) and "word" in outer:
                        items.append(outer)
                for idx, item in enumerate(items):
                    word = item.get("word", item.get("query", ""))
                    if not word:
                        continue
                    # 百度热搜无 hotScore 字段，用倒序 index 模拟热度
                    raw_score = float(item.get("hotScore", item.get("rawHotScore", 0)))
                    hot_score = raw_score if raw_score > 0 else max(10000 - idx * 100, 0)
                    topics.append(CollectedTopic(
                        title=word,
                        source="baidu",
                        hot_score=hot_score,
                        summary=item.get("desc", ""),
                        source_url=item.get("url", item.get("rawUrl", "")),
                    ))

            logger.info("百度热搜采集完成，共 %d 条", len(topics))
            return sorted(topics, key=lambda t: t.hot_score, reverse=True)[:20]

        except Exception as exc:
            logger.error("百度热搜采集失败: %s", exc)
            return []
