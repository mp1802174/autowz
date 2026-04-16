import asyncio
import logging
from difflib import SequenceMatcher

from app.services.collector.baidu import BaiduCollector
from app.services.collector.base import CollectedTopic
from app.services.collector.weibo import WeiboCollector

logger = logging.getLogger("autowz.collector")


class CollectorManager:
    """管理多个采集器，并发采集、去重合并。"""

    def __init__(self) -> None:
        self.collectors = [WeiboCollector(), BaiduCollector()]

    async def collect_all(self) -> list[CollectedTopic]:
        results = await asyncio.gather(
            *[c.collect() for c in self.collectors],
            return_exceptions=True,
        )
        all_topics: list[CollectedTopic] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("采集器出错: %s", result)
                continue
            all_topics.extend(result)

        deduped = self._deduplicate(all_topics)
        deduped.sort(key=lambda t: t.hot_score, reverse=True)
        logger.info("采集合并完成：原始 %d 条 → 去重后 %d 条", len(all_topics), len(deduped))
        return deduped

    @staticmethod
    def _deduplicate(topics: list[CollectedTopic], threshold: float = 0.7) -> list[CollectedTopic]:
        """按标题相似度去重，保留热度更高的一条。"""
        kept: list[CollectedTopic] = []
        for topic in sorted(topics, key=lambda t: t.hot_score, reverse=True):
            is_dup = False
            for existing in kept:
                ratio = SequenceMatcher(None, topic.title, existing.title).ratio()
                if ratio >= threshold:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(topic)
        return kept
