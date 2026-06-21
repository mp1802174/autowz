import logging
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.services.wechat.exceptions import WechatAPIError
from typing import Optional

logger = logging.getLogger("autowz.wechat.client")

# Token 过期相关的错误码，需要刷新 token 后重试
TOKEN_EXPIRED_CODES = {40001, 40014, 42001}


class WechatClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.wechat_base_url.rstrip("/")
        self.timeout = 30.0

    @staticmethod
    def _check_response(data: dict) -> dict:
        """检查微信 API 响应，errcode != 0 时抛出异常。"""
        errcode = data.get("errcode", 0)
        if errcode != 0:
            errmsg = data.get("errmsg", "unknown error")
            raise WechatAPIError(errcode, errmsg)
        return data

    async def get(self, path: str, params: Optional[dict] = None) -> dict:
        # 微信API不走代理,使用本机真实IP
        # httpx 0.28 使用 trust_env=False 禁用环境变量代理
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            trust_env=False  # 禁用环境变量代理
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            data = response.json()
        return self._check_response(data)

    async def post_json(
        self, path: str, params: Optional[dict] = None, json_body: Optional[dict] = None,
    ) -> dict:
        # 微信API不走代理,使用本机真实IP
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            trust_env=False  # 禁用环境变量代理
        ) as client:
            response = await client.post(path, params=params, json=json_body)
            response.raise_for_status()
            data = response.json()
        return self._check_response(data)

    async def post_multipart(
        self,
        path: str,
        params: Optional[dict] = None,
        file_path: str | Path = "",
        field_name: str = "media",
    ) -> dict:
        """上传文件到微信 API（multipart/form-data）。"""
        fp = Path(file_path)
        if not fp.exists():
            raise ValueError(f"文件不存在: {file_path}")

        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif"}
        mime = mime_map.get(fp.suffix.lower(), "application/octet-stream")

        # 微信API不走代理,使用本机真实IP
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=60.0,
            trust_env=False  # 禁用环境变量代理
        ) as client:
            with open(fp, "rb") as f:
                files = {field_name: (fp.name, f, mime)}
                response = await client.post(path, params=params, files=files)
            response.raise_for_status()
            data = response.json()
        return self._check_response(data)
