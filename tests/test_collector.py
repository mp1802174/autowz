import pytest
from unittest.mock import AsyncMock, patch

from app.services.collector.base import CollectedTopic
from app.services.collector.manager import CollectorManager
from app.services.collector.search import NewsItem, _dedup_by_similarity


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


class TestNewsPoolSimilarityDedup:
    def test_near_synonym_titles_clustered(self):
        items = [
            NewsItem(title="多地上调养老金 退休人员待遇提升", description="短"),
            NewsItem(title="多地养老金上调 退休人员待遇迎来提升", description="更长的描述更全面"),
            NewsItem(title="一季度GDP数据公布 经济温和回升", description=""),
        ]
        result = _dedup_by_similarity(items)
        titles = [it.title for it in result]
        # 两条养老金近义标题合并为一，GDP 独立保留
        assert len(result) == 2
        assert "一季度GDP数据公布 经济温和回升" in titles

    def test_keeps_longer_description(self):
        items = [
            NewsItem(title="某地发布楼市新政 优化购房政策", description="短"),
            NewsItem(title="某地楼市新政发布 购房政策优化", description="信息更全的长描述内容"),
        ]
        result = _dedup_by_similarity(items)
        assert len(result) == 1
        assert result[0].description == "信息更全的长描述内容"

    def test_distinct_topics_untouched(self):
        items = [
            NewsItem(title="央行宣布降准释放流动性"),
            NewsItem(title="多地暴雨红色预警发布"),
        ]
        result = _dedup_by_similarity(items)
        assert len(result) == 2
