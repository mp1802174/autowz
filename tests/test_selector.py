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


def test_llm_max_items_configurable():
    """llm_max_items 可注入，覆盖默认值。"""
    selector = TopicSelectorService(llm_max_items=10)
    assert selector.llm_max_items == 10


def test_sports_game_no_longer_hard_filtered():
    """放宽后体育/游戏不再被硬过滤，仅靠 downrank 降权后仍可入选。"""
    items = [
        NewsItem(title="某足球俱乐部商业估值大涨 产业资本入局", description="体育产业经济角度"),
        NewsItem(title="某游戏公司营收创新高 电竞产业升温", description="游戏产业经济"),
    ]
    selector = TopicSelectorService(
        blacklist_keywords=["明星", "八卦", "绯闻", "恋情", "离婚", "综艺"],
    )
    result = selector._fallback_select(items, short_count=2, long_count=0)
    # 体育/游戏不在黑名单，未被一刀切，仍进入候选
    assert len(result["short"]) == 2


def test_fallback_dedups_near_synonyms():
    """兜底选题对近义重复主题去重，不会同时选出同一事件两条。"""
    items = [
        NewsItem(title="多地上调养老金 退休待遇提升", description="社保养老民生"),
        NewsItem(title="多地养老金上调 退休待遇迎提升", description="社保养老民生保障"),
        NewsItem(title="一季度CPI公布 消费温和回升", description="物价消费数据"),
    ]
    selector = TopicSelectorService()
    result = selector._fallback_select(items, short_count=2, long_count=0)
    titles = [it.title for it in result["short"]]
    # 两条养老金近义合并，选出的两条不应都是养老金
    assert not (all("养老金" in t for t in titles))
