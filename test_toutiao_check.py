"""诊断头条号账号状态 —— 检查是否需要完善信息/实名认证。"""
import asyncio
import logging

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    state_path = "app/services/publish/cookies/toutiao_state.json"

    print("\n=== 诊断头条号账号状态 ===\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 可见模式，便于观察
        context = await browser.new_context(storage_state=state_path)
        page = await context.new_page()

        # 1. 访问首页
        print("1. 正在访问头条号首页...")
        await page.goto("https://mp.toutiao.com/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        # 2. 检查是否有认证提示
        print("2. 检查页面状态...")
        title = await page.title()
        url = page.url
        print(f"   当前页面标题: {title}")
        print(f"   当前页面URL: {url}")

        # 3. 尝试访问发布页
        print("\n3. 尝试访问图文发布页...")
        await page.goto("https://mp.toutiao.com/profile_v4/graphic/publish",
                       wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        publish_title = await page.title()
        publish_url = page.url
        print(f"   发布页标题: {publish_title}")
        print(f"   发布页URL: {publish_url}")

        # 4. 检查是否有错误提示或认证要求
        error_texts = await page.evaluate("""() => {
            const texts = [];
            // 检查常见的错误/提示元素
            document.querySelectorAll('.error, .warning, .notice, .alert').forEach(el => {
                texts.push(el.innerText.trim());
            });
            // 检查是否有"完善信息"之类的提示
            const bodyText = document.body.innerText;
            if (bodyText.includes('完善') || bodyText.includes('认证') || bodyText.includes('实名')) {
                texts.push('页面包含认证相关关键词');
            }
            return texts;
        }""")

        if error_texts:
            print("\n⚠️  发现提示信息:")
            for txt in error_texts:
                print(f"   - {txt}")

        # 5. 截图保存
        screenshot_path = "/tmp/toutiao_publish_page.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"\n📷 页面截图已保存: {screenshot_path}")

        print("\n请检查浏览器窗口，查看是否有:")
        print("  1. 需要完善资料的提示")
        print("  2. 需要实名认证的提示")
        print("  3. 账号状态异常的提示")
        print("\n按 Ctrl+C 结束诊断...")

        # 保持浏览器打开，便于人工检查
        try:
            await page.wait_for_timeout(300000)  # 等待5分钟
        except KeyboardInterrupt:
            print("\n诊断结束")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
