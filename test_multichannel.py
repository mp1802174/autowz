"""多渠道发布端到端测试 — 通过 PublishRouter 同时发到头条+百家号"""
import asyncio
import logging

from app.services.publish import (
    ArticleProduct,
    BaijiahaoChannel,
    PublishRouter,
    ToutiaoChannel,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main():
    product = ArticleProduct(
        title="多渠道发布系统端到端验证",
        digest="验证 PublishRouter 同时分发到多个渠道",
        content_html="<p>这是多渠道发布系统的端到端测试。</p><p>本文将同时保存为头条号和百家号的草稿。</p>",
        content_md="这是多渠道发布系统的端到端测试。\n\n本文将同时保存为头条号和百家号的草稿。",
        author="现象观察",
        ai_disclosure=True,
        quality_score=85.0,
    )

    router = PublishRouter(
        channels=[ToutiaoChannel(), BaijiahaoChannel()],
        min_quality=0.0,
    )

    print(f"已注册渠道: {router.channels}")
    targets = ["toutiao", "baijiahao"]

    print(f"\n=== 开始多渠道发布 → {targets} ===")
    results = await router.publish(product, targets=targets, as_draft=True)

    print("\n=== 发布结果 ===")
    for ch_name, r in results.items():
        status = "OK" if r.ok else "FAIL"
        print(f"  [{status}] {ch_name}: status={r.status} draft_id={r.draft_id} error={r.error}")

    all_ok = all(r.ok for r in results.values())
    print(f"\n{'全部成功' if all_ok else '部分失败'}")


if __name__ == "__main__":
    asyncio.run(main())
