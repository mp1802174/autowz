"""测试头条号发布功能 —— 发布一篇测试文章到草稿箱。"""
import asyncio
import logging

from app.services.publish.channels.toutiao import ToutiaoChannel
from app.services.publish.product import ArticleProduct

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def main():
    # 1. 创建测试产物
    test_article = ArticleProduct(
        title="测试文章 - 头条号发布功能验证",
        digest="这是一篇用于验证自动发布系统的测试文章",
        content_html="<p>这是测试内容的第一段。</p><p>这是第二段，用于验证发布流程。</p>",
        content_md="这是测试内容的第一段。\n\n这是第二段，用于验证发布流程。",
        author="现象观察",
        ai_disclosure=True,
        quality_score=85.0,
    )

    # 2. 初始化头条渠道
    channel = ToutiaoChannel()

    # 3. 检查登录态
    print("\n=== 检查头条号登录态 ===")
    is_ready = await channel.is_ready()
    print(f"登录态状态: {'✅ 就绪' if is_ready else '❌ 未就绪'}")

    if not is_ready:
        print("\n⚠️  登录态无效，请运行以下命令重新获取:")
        print("   python scripts/login_helper.py toutiao")
        return

    # 4. 发布到草稿
    print("\n=== 开始发布测试文章到头条草稿箱 ===")
    print("提示：如果失败显示 err_no=7050，通常需要：")
    print("  1. 登录头条号后台: https://mp.toutiao.com/")
    print("  2. 完成账号实名认证")
    print("  3. 完善头条号基本信息（昵称、简介、头像等）")
    print("  4. 重新导出登录态: python scripts/login_helper.py toutiao\n")
    result = await channel.publish(test_article, as_draft=True)

    # 5. 输出结果
    print("\n=== 发布结果 ===")
    print(f"渠道: {result.channel}")
    print(f"成功: {'✅' if result.ok else '❌'}")
    print(f"状态: {result.status}")
    if result.draft_id:
        print(f"草稿ID: {result.draft_id}")
    if result.error:
        print(f"错误: {result.error}")
    if result.skipped_reason:
        print(f"跳过原因: {result.skipped_reason}")

    if result.ok:
        print("\n✅ 测试成功！请登录头条号后台查看草稿箱: https://mp.toutiao.com/profile_v4/graphic/content-manage")
    else:
        print("\n❌ 测试失败，请检查上述错误信息")


if __name__ == "__main__":
    asyncio.run(main())
