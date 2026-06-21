"""
微信公众平台后台「内部接口」客户端。

非微信开放平台 API，需要在 mp.weixin.qq.com 扫码登录后拿到的 token+cookie。
本模块复用 newwz 项目维护的登录凭据文件，按公众号名称查询 fakeid 并拉取已发布文章列表。

调用频率：每日 ≤ 20 次，超出会被腾讯风控。
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import httpx
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("autowz.wechat.mp_backend")

DEFAULT_AUTH_PATH = "/root/cc/newwz/data/id_info.json"
DEFAULT_FAKEID_CACHE = "/root/cc/autowz/data/wechat_mp_fakeid.json"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class MpBackendError(Exception):
    """微信公众平台后台接口错误。"""


class MpBackendAuthExpired(MpBackendError):
    """登录凭据已过期，需要重新扫码。"""


class WechatMpBackend:
    def __init__(
        self,
        auth_path: str = DEFAULT_AUTH_PATH,
        fakeid_cache: str = DEFAULT_FAKEID_CACHE,
    ) -> None:
        self.auth_path = Path(auth_path)
        self.fakeid_cache_path = Path(fakeid_cache)
        self.fakeid_cache_path.parent.mkdir(parents=True, exist_ok=True)

    # ─── 凭据 ───────────────────────────────────────────────────────────

    def _load_auth(self) -> Tuple[str, str]:
        if not self.auth_path.exists():
            raise MpBackendAuthExpired(
                f"凭据文件不存在: {self.auth_path}，请在 newwz 项目扫码登录"
            )
        data = json.loads(self.auth_path.read_text(encoding="utf-8"))
        token = data.get("token", "")
        cookie = data.get("cookie", "")
        if not token or not cookie:
            raise MpBackendAuthExpired("凭据文件缺少 token 或 cookie")
        return token, cookie

    def _headers(self, cookie: str) -> dict:
        return {
            "User-Agent": _USER_AGENT,
            "Referer": "https://mp.weixin.qq.com/",
            "Cookie": cookie,
        }

    def _check_resp(self, resp: dict) -> None:
        base = resp.get("base_resp", {})
        ret = base.get("ret", 0)
        if ret == 0:
            return
        msg = base.get("err_msg", "")
        # 常见错误码：200003 invalid session（凭据过期）、200013 freq control
        if ret in (200002, 200003, 200012, 200013):
            if "session" in msg or ret == 200003:
                raise MpBackendAuthExpired(f"登录凭据已过期: ret={ret} msg={msg}")
            raise MpBackendError(f"接口被风控/频率限制: ret={ret} msg={msg}")
        raise MpBackendError(f"接口返回错误: ret={ret} msg={msg}")

    # ─── fakeid 缓存 ────────────────────────────────────────────────────

    def _load_fakeid_cache(self) -> dict:
        if not self.fakeid_cache_path.exists():
            return {}
        try:
            return json.loads(self.fakeid_cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_fakeid_cache(self, cache: dict) -> None:
        self.fakeid_cache_path.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ─── 接口 ───────────────────────────────────────────────────────────

    async def get_fakeid(self, account_name: str) -> str:
        cache = self._load_fakeid_cache()
        if account_name in cache:
            return cache[account_name]

        token, cookie = self._load_auth()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://mp.weixin.qq.com/cgi-bin/searchbiz",
                params={
                    "action": "search_biz", "begin": 0, "count": 5,
                    "query": account_name, "token": token,
                    "lang": "zh_CN", "f": "json", "ajax": 1,
                },
                headers=self._headers(cookie),
            )
        data = resp.json()
        self._check_resp(data)

        for item in data.get("list", []):
            if item.get("nickname") == account_name:
                fakeid = item["fakeid"]
                cache[account_name] = fakeid
                self._save_fakeid_cache(cache)
                logger.info("公众号 [%s] fakeid=%s 已缓存", account_name, fakeid)
                return fakeid

        raise MpBackendError(f"找不到公众号: {account_name}")

    async def list_published_articles(
        self,
        account_name: Optional[str] = None,
        limit: int = 200,
    ) -> List[dict]:
        """
        拉取"已发布"文章列表。

        account_name=None（默认/推荐）：以当前登录账号管理员视角拉自己号的全部已发表文章，
          走 /cgi-bin/appmsgpublish 不带 fakeid 路径，可拉到完整列表。
        account_name 传值：以"外部号"视角查询指定名称的公众号已发表列表（被微信限制，
          通常只返回 2 条左右；除非业务上确实要看别人的号，否则不要传）。

        单次接口返回 5 条，按 begin 翻页。返回每项：
        {title, article_url, cover, publish_at(datetime), aid}
        """
        token, cookie = self._load_auth()

        base_params: Dict[str, object] = {
            "sub": "list", "search_field": "null", "query": "",
            "type": "101_1", "free_publish_type": 1,
            "sub_action": "list_ex", "token": token,
            "lang": "zh_CN", "f": "json", "ajax": 1,
        }
        if account_name is not None:
            base_params["fakeid"] = await self.get_fakeid(account_name)

        results: List[dict] = []
        page_size = 5
        async with httpx.AsyncClient(timeout=20) as client:
            for begin in range(0, limit, page_size):
                params = {**base_params, "begin": begin, "count": page_size}
                resp = await client.get(
                    "https://mp.weixin.qq.com/cgi-bin/appmsgpublish",
                    params=params,
                    headers=self._headers(cookie),
                )
                data = resp.json()
                self._check_resp(data)

                publish_page = json.loads(data.get("publish_page", "{}"))
                total = publish_page.get("total_count", 0)
                publish_list = publish_page.get("publish_list", [])
                if not publish_list:
                    return results

                for item in publish_list:
                    info = json.loads(item.get("publish_info", "{}"))
                    for art in info.get("appmsgex", []):
                        if art.get("is_deleted"):
                            continue
                        create_time = art.get("create_time")
                        link = art.get("link") or ""
                        if not link or not create_time:
                            continue
                        results.append({
                            "aid": art.get("aid", ""),
                            "title": (art.get("title") or "").strip(),
                            "article_url": link,
                            "cover": art.get("cover", ""),
                            "publish_at": datetime.fromtimestamp(create_time),
                        })
                        if len(results) >= limit:
                            return results

                if begin + page_size >= total:
                    break

        return results
