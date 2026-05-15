import pytest

from app.services.collector.search import NewsItem
from app.services.selector.service import TopicSelectorService


def test_fallback_prioritizes_finance_and_international_topics():
    items = [
        NewsItem(title="某明星演唱会绯闻持续发酵", description="八卦热搜引发吃瓜", source="weibo"),
        NewsItem(title="美联储降息预期升温 全球股市波动", description="市场关注美元、利率与就业数据", source="rss"),
        NewsItem(title="两国元首会晤 聚焦关税与供应链合作", description="国际关系与经贸议题升温", source="rss"),
    ]

    result = TopicSelectorService._fallback_select(items, short_count=2, long_count=0)

    assert [item.title for item in result["short"]] == [
        "两国元首会晤 聚焦关税与供应链合作",
        "美联储降息预期升温 全球股市波动",
    ]


def test_priority_score_downranks_entertainment_gossip():
    gossip = NewsItem(title="某明星恋情曝光", description="吃瓜热搜", source="weibo")
    finance = NewsItem(title="一季度GDP与消费数据发布", description="宏观经济恢复", source="rss")

    assert TopicSelectorService._priority_score(finance) > TopicSelectorService._priority_score(gossip)