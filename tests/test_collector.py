import pytest
from unittest.mock import AsyncMock, patch

from app.services.collector.base import CollectedTopic
from app.services.collector.manager import CollectorManager


def _make_topic(title: str, source: str, score: float) -> CollectedTopic:
    return CollectedTopic(title=title, source=source, hot_score=score, summary="")


class TestCollectorManager:
    def test_deduplicate_exact(self):
        topics = [
            _make_topic("热点A", "weibo", 100),
            _make_topic("热点A", "baidu", 80),
        ]
        result = CollectorManager._deduplicate(topics)
        assert len(result) == 1
        assert result[0].hot_score == 100

    def test_deduplicate_similar(self):
        topics = [
            _make_topic("某明星离婚了", "weibo", 100),
            _make_topic("某明星离婚", "baidu", 80),
        ]
        result = CollectorManager._deduplicate(topics, threshold=0.7)
        assert len(result) == 1

    def test_deduplicate_different(self):
        topics = [
            _make_topic("经济数据发布", "weibo", 100),
            _make_topic("明星八卦事件", "baidu", 80),
        ]
        result = CollectorManager._deduplicate(topics, threshold=0.7)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_collect_all_with_mock(self):
        manager = CollectorManager()
        weibo_topics = [_make_topic("微博热搜1", "weibo", 100)]
        baidu_topics = [_make_topic("百度热搜1", "baidu", 90)]

        with patch.object(manager.collectors[0], "collect", new_callable=AsyncMock, return_value=weibo_topics), \
             patch.object(manager.collectors[1], "collect", new_callable=AsyncMock, return_value=baidu_topics):
            result = await manager.collect_all()

        assert len(result) == 2
        assert result[0].hot_score >= result[1].hot_score
