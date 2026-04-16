import asyncio
import json
import logging

from functools import lru_cache

from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger("autowz.llm")


class LLMClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.default_model = settings.openai_model

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> str:
        """调用 LLM 生成文本，内置重试机制。"""
        model = model or self.default_model
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                # 使用 stream 模式，因为部分 API 代理在非流式模式下不返回 content
                stream = await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
                chunks: list[str] = []
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        chunks.append(chunk.choices[0].delta.content)
                content = "".join(chunks)
                logger.info(
                    "LLM 调用成功: model=%s, 输出长度=%d",
                    model, len(content),
                )
                return content
            except Exception as exc:
                last_error = exc
                wait = 2 ** attempt
                logger.warning("LLM 调用失败 (attempt %d/3): %s, %ds 后重试", attempt + 1, exc, wait)
                await asyncio.sleep(wait)

        raise RuntimeError(f"LLM 调用 3 次均失败: {last_error}") from last_error

    async def json_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> dict:
        """调用 LLM 并解析 JSON 响应。"""
        system_prompt += "\n\n请只输出合法 JSON，不要包含 markdown 代码块标记或任何其他文字。"
        raw = await self.chat_completion(
            system_prompt, user_prompt,
            temperature=temperature, max_tokens=max_tokens, model=model,
        )
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(raw: str) -> dict:
        """从 LLM 输出中提取 JSON，兼容思维过程等额外文本。"""
        text = raw.strip()

        # 去掉 markdown 代码块
        if text.startswith("```"):
            first_newline = text.index("\n")
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # 直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 找最外层的 { ... }
        start = text.find("{")
        if start >= 0:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break

        raise json.JSONDecodeError("无法从 LLM 输出中提取 JSON", text, 0)


@lru_cache
def get_llm_client() -> LLMClient:
    return LLMClient()
