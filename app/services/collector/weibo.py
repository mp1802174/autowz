import logging
from urllib.parse import quote

import httpx

from app.services.collector.base import BaseCollector, CollectedTopic

logger = logging.getLogger("autowz.collector.weibo")


class WeiboCollector(BaseCollector):
    """微博热搜采集器。"""

    URL = "https://weibo.com/ajax/side/hotSearch"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://weibo.com/",
    }

    async def collect(self) -> list[CollectedTopic]:
        try:
            async with httpx.AsyncClient(timeout=15, headers=self.HEADERS) as client:
                resp = await client.get(self.URL)
                resp.raise_for_status()
                data = resp.json()

            realtime = data.get("data", {}).get("realtime", [])
            topics: list[CollectedTopic] = []
            for item in realtime[:30]:
                word = item.get("word", "")
                if not word:
                    continue
                topics.append(CollectedTopic(
                    title=word,
                    source="weibo",
                    hot_score=float(item.get("raw_hot", item.get("num", 0))),
                    summary=item.get("label_name", ""),
                    source_url=f"https://s.weibo.com/weibo?q=%23{quote(word)}%23",
                ))

            logger.info("微博热搜采集完成，共 %d 条", len(topics))
            return sorted(topics, key=lambda t: t.hot_score, reverse=True)[:20]

        except Exception as exc:
            logger.error("微博热搜采集失败: %s", exc)
            return []
