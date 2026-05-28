"""逐个测试 image_providers.json 中每个 model 的可达性 + 生图能力。

用法:
    python scripts/test_image_providers.py [--timeout 90]

产物:
    tmp_image_test/<provider>__<model>.jpg     - 成功时保存的生图
    控制台输出每个 model 的 OK / TIMEOUT / FAIL 状态、耗时、错误摘要
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.services.wechat.cover_generator import (  # noqa: E402
    _build_image_providers,
    _generate_with_provider,
)

PROMPT = "生成一张在优美风景中的美女图片"
OUT_DIR = Path(__file__).resolve().parent.parent / "tmp_image_test"


def _safe_name(provider: dict) -> str:
    name = (provider.get("name") or "?").replace("/", "_")
    model = (provider["model"] or "?").replace("/", "_")
    return f"{name}__{model}"


async def test_one(provider: dict, timeout_s: float) -> dict:
    label = _safe_name(provider)
    out_file = OUT_DIR / f"{label}.jpg"
    started = time.monotonic()
    try:
        timeout_cfg = httpx.Timeout(timeout_s, connect=20.0)
        async with httpx.AsyncClient(timeout=timeout_cfg) as client:
            img_bytes = await asyncio.wait_for(
                _generate_with_provider(client, provider, PROMPT),
                timeout=timeout_s,
            )
        out_file.write_bytes(img_bytes)
        return {
            "label": label,
            "status": "OK",
            "elapsed": time.monotonic() - started,
            "size": len(img_bytes),
            "path": str(out_file),
        }
    except asyncio.TimeoutError:
        return {
            "label": label,
            "status": "TIMEOUT",
            "elapsed": time.monotonic() - started,
            "err": f"超过 {timeout_s}s",
        }
    except Exception as exc:
        return {
            "label": label,
            "status": "FAIL",
            "elapsed": time.monotonic() - started,
            "err": f"{type(exc).__name__}: {exc}"[:500],
        }


async def main(timeout_s: float) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    settings = get_settings()
    providers = _build_image_providers(settings)
    if not providers:
        print("没有可用 provider，请检查 image_providers.json")
        return

    print(f"共 {len(providers)} 个 model 条目，并发测试 (单调用超时 {timeout_s:.0f}s)\n")
    for p in providers:
        print(f"  - {_safe_name(p):55s}  url={p['api_url']}")
    print()

    results = await asyncio.gather(*(test_one(p, timeout_s) for p in providers))

    print("\n========== 结果 ==========")
    ok = fail = timeout = 0
    for r in results:
        if r["status"] == "OK":
            ok += 1
            print(
                f"[OK]      {r['label']:55s} {r['elapsed']:6.1f}s  "
                f"{r['size']/1024:7.1f}KB  -> {r['path']}"
            )
        elif r["status"] == "TIMEOUT":
            timeout += 1
            print(
                f"[TIMEOUT] {r['label']:55s} {r['elapsed']:6.1f}s  {r['err']}"
            )
        else:
            fail += 1
            print(
                f"[FAIL]    {r['label']:55s} {r['elapsed']:6.1f}s  {r['err']}"
            )
    print(f"\n合计 OK={ok} FAIL={fail} TIMEOUT={timeout}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()
    asyncio.run(main(args.timeout))
