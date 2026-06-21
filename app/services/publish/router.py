"""发布路由 —— 把一篇 ArticleProduct 按配置分发到多个渠道。

# ⚠️ 项目第一纲领(不可违背 —— 换任何开发者/维护者/AI 都须第一时间遵循):
#    质量第一,质量低不如不做。本路由内置"质量门":quality_score 低于阈值的产物
#    一律拒发(所有渠道),把"质量低不如不做"焊进发布主路径。
#    走质量路线,不走规避路线。详见 README 顶部纲领 与 GUIDE.md §8.3。
"""
from __future__ import annotations

import logging

from app.services.publish.base import Channel
from app.services.publish.product import ArticleProduct, PublishResult
from typing import Dict, List, Optional

logger = logging.getLogger("autowz.publish.router")


class PublishRouter:
    """渠道注册表 + 分发器。质量门 + 草稿优先 + 单渠道失败隔离。"""

    def __init__(self, channels: Optional[List[Channel]] = None, min_quality: float = 0.0) -> None:
        self._channels: Dict[str, Channel] = {}
        self.min_quality = min_quality
        for ch in channels or []:
            self.register(ch)

    def register(self, channel: Channel) -> None:
        self._channels[channel.name] = channel

    @property
    def channels(self) -> List[str]:
        return list(self._channels)

    async def publish(
        self,
        product: ArticleProduct,
        targets: List[str],
        *,
        as_draft: bool = True,
    ) -> Dict[str, PublishResult]:
        """把 product 发布到 targets 指定的各渠道,返回 {渠道名: 结果}。"""
        results: Dict[str, PublishResult] = {}

        # 质量门:不达标则全部拒发(第一纲领:质量低不如不做)
        if product.quality_score is not None and product.quality_score < self.min_quality:
            reason = f"质量分 {product.quality_score} < 阈值 {self.min_quality},按第一纲领拒发"
            logger.warning("质量门拦截: %s(title=%s)", reason, product.title)
            for name in targets:
                results[name] = PublishResult(
                    channel=name, ok=False, status="blocked_low_quality", skipped_reason=reason
                )
            return results

        for name in targets:
            channel = self._channels.get(name)
            if channel is None:
                results[name] = PublishResult(
                    channel=name, ok=False, status="unknown_channel", skipped_reason="渠道未注册"
                )
                continue
            try:
                if not await channel.is_ready():
                    results[name] = PublishResult(
                        channel=name, ok=False, status="not_ready",
                        skipped_reason="渠道未就绪(登录态/配置无效)",
                    )
                    continue
                results[name] = await channel.publish(product, as_draft=as_draft)
            except Exception as exc:  # 单渠道失败不影响其他渠道
                logger.exception("渠道 %s 发布异常", name)
                results[name] = PublishResult(channel=name, ok=False, status="error", error=str(exc))
        return results
