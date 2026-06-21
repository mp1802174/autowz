"""各平台渠道实现。新增平台时在此目录加一个 Channel 子类并导出。"""
from app.services.publish.channels.baijiahao import BaijiahaoChannel
from app.services.publish.channels.playwright_base import PlaywrightChannel
from app.services.publish.channels.toutiao import ToutiaoChannel
from app.services.publish.channels.wechat import WechatChannel

__all__ = ["WechatChannel", "PlaywrightChannel", "ToutiaoChannel", "BaijiahaoChannel"]
