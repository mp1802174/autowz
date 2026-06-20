"""登录态导出助手 —— 在【你本地有图形界面的电脑】上运行,不是服务器。

作用:打开浏览器让你手动登录(扫码/账密),把登录态导出成 storage_state 文件,
再把该文件传到服务器的 app/services/publish/cookies/ 下,autowz 即可用它无人值守发布。
登录态过期后(通常数周)重跑一次即可。

依赖:pip install playwright && playwright install chromium

用法:
    python scripts/login_helper.py toutiao
    python scripts/login_helper.py baijiahao
    python scripts/login_helper.py dayu
"""
from __future__ import annotations

import asyncio
import os
import sys

from playwright.async_api import async_playwright

TARGETS = {
    "toutiao": "https://mp.toutiao.com/",
    "baijiahao": "https://baijiahao.baidu.com/builder/rc/home",
    "dayu": "https://mp.dayu.com/",
}

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "services", "publish", "cookies")


async def main(platform: str) -> None:
    if platform not in TARGETS:
        print(f"未知平台: {platform};可选: {', '.join(TARGETS)}")
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.normpath(os.path.join(OUT_DIR, f"{platform}_state.json"))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 本地有界面,便于扫码
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(TARGETS[platform])
        print(f"\n请在弹出的浏览器里登录【{platform}】(扫码/账密)。")
        input("登录完成后,回到这里按回车导出登录态... ")
        await context.storage_state(path=out)
        print(f"✅ 已导出登录态: {out}")
        print("   把这个文件传到服务器同路径 app/services/publish/cookies/ 即可。")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "toutiao"))
