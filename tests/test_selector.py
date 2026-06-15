import pytest

from app.services.collector.search import NewsItem
from app.services.selector.service import TopicSelectorService


def test_fallback_prioritizes_finance_and_livelihood_topics():
    items = [
        NewsItem(title="某明星演唱会绯闻持续发酵", description="八卦热搜引发吃瓜", source="weibo"),
        NewsItem(title="一季度CPI公布 居民消费温和回升", description="物价与消费数据备受关注", source="rss"),
        NewsItem(title="多地上调养老金 退休职工待遇提升", description="社保养老与民生保障升温", source="rss"),
    ]

    result = TopicSelectorService()._fallback_select(items, short_count=2, long_count=0)

    assert [item.title for item in result["short"]] == [
        "一季度CPI公布 居民消费温和回升",
        "多地上调养老金 退休职工待遇提升",
    ]


def test_priority_score_downranks_entertainment_gossip():
    gossip = NewsItem(title="某明星恋情曝光", description="吃瓜热搜", source="weibo")
    finance = NewsItem(title="一季度GDP与消费数据发布", description="宏观经济恢复", source="rss")

    selector = TopicSelectorService()
    assert selector._priority_score(finance) > selector._priority_score(gossip)
