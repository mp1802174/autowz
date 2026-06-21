"""解耦发布层:生成层产出 ArticleProduct → PublishRouter → 各 Channel。

设计见 docs/multichannel_plan.md。第一纲领(质量第一)通过 Router 的质量门落地。
"""
from app.services.publish.base import Channel
from app.services.publish.channels.baijiahao import BaijiahaoChannel
from app.services.publish.channels.playwright_base import PlaywrightChannel
from app.services.publish.channels.toutiao import ToutiaoChannel
from app.services.publish.channels.wechat import WechatChannel
from app.services.publish.product import ArticleProduct, ChannelStats, PublishResult
from app.services.publish.router import PublishRouter

__all__ = [
    "ArticleProduct",
    "PublishResult",
    "ChannelStats",
    "Channel",
    "PublishRouter",
    "WechatChannel",
    "PlaywrightChannel",
    "ToutiaoChannel",
    "BaijiahaoChannel",
]
