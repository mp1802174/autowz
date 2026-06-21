"""渠道(Channel)抽象 —— 发布层的核心接口。

每个平台(微信 / 头条 / 百家 / 大鱼 …)实现一个 Channel;生成与发布彻底解耦,
任意已注册渠道都能通过 PublishRouter 自由组合。新增平台 = 新增一个 Channel 实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.publish.product import ArticleProduct, ChannelStats, PublishResult


class Channel(ABC):
    """一个发布渠道的统一接口。"""

    #: 渠道唯一标识(如 "wechat" / "toutiao")
    name: str = ""

    @abstractmethod
    async def is_ready(self) -> bool:
        """渠道是否就绪:配置 / 登录态 / Cookie 是否有效。未就绪则 Router 跳过它。"""

    @abstractmethod
    async def publish(self, product: ArticleProduct, *, as_draft: bool = True) -> PublishResult:
        """发布一篇文章。默认草稿优先(as_draft=True),降低风控与误发风险。"""

    async def fetch_stats(self, ref: str) -> Optional[ChannelStats]:
        """回收该渠道某篇文章的数据(阅读 / 点赞等)。默认未实现,P2 数据闭环时按渠道补。"""
        return None
