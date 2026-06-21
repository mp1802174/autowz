"""测试百家号发布功能 — 发布一篇测试文章到草稿箱。"""
import asyncio
import logging

from app.services.publish.channels.baijiahao import BaijiahaoChannel
from app.services.publish.product import ArticleProduct

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main():
    test_article = ArticleProduct(
        title="百家号发布功能验证-自动化测试",
        digest="这是一篇用于验证自动发布系统的测试文章",
        content_html="<p>这是百家号渠道自动化测试内容的第一段。</p><p>第二段验证文字。系统将通过 API 保存此文章为草稿。</p>",
        content_md="这是百家号渠道自动化测试内容的第一段。\n\n第二段验证文字。系统将通过 API 保存此文章为草稿。",
        author="现象观察",
        ai_disclosure=True,
        quality_score=85.0,
    )

    channel = BaijiahaoChannel()

    print("\n=== 检查百家号登录态 ===")
    is_ready = await channel.is_ready()
    print(f"登录态状态: {'就绪' if is_ready else '未就绪'}")
    if not is_ready:
        print("缺少登录态,请先导出 baijiahao_state.json")
        return

    print("\n=== 开始发布测试文章到百家号草稿箱 ===")
    result = await channel.publish(test_article, as_draft=True)

    print("\n=== 发布结果 ===")
    print(f"渠道: {result.channel}")
    print(f"成功: {'yes' if result.ok else 'no'}")
    print(f"状态: {result.status}")
    if result.draft_id:
        print(f"草稿ID: {result.draft_id}")
    if result.error:
        print(f"错误: {result.error}")

    if result.ok:
        print("\n测试成功！请登录百家号后台查看草稿: https://baijiahao.baidu.com/builder/rc/content")
    else:
        print("\n测试失败，请检查上述错误信息")


if __name__ == "__main__":
    asyncio.run(main())
