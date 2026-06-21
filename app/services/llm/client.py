import asyncio
import json
import logging

from functools import lru_cache
from typing import List, Optional, Tuple

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

        # 解析 fallback 模型列表
        fallback_str = settings.llm_fallback_models.strip()
        self.fallback_models = [m.strip() for m in fallback_str.split(",") if m.strip()] if fallback_str else []
        logger.info("LLM fallback 模型链: %s", " → ".join(self.fallback_models) if self.fallback_models else "无")

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
    ) -> str:
        """调用 LLM 生成文本，内置重试机制 + fallback 模型切换。

        frequency_penalty/presence_penalty 用于降低用词重复、提升多样性；
        仅在 > 0 时传给后端，避免给不支持该参数的代理发送。

        Fallback 机制:
        1. 先用指定模型重试 3 次
        2. 失败后按 fallback_models 顺序依次尝试其他模型(每个也重试 3 次)
        3. 所有模型都失败才抛出异常
        """
        target_model = model or self.default_model
        models_to_try = [target_model] + [m for m in self.fallback_models if m != target_model]

        all_errors: List[Tuple[str, Exception]] = []

        for model_idx, current_model in enumerate(models_to_try):
            if model_idx > 0:
                logger.warning(
                    "主模型 %s 失败,切换到 fallback 模型 %s (%d/%d)",
                    target_model, current_model, model_idx, len(models_to_try) - 1,
                )

            for attempt in range(3):
                try:
                    # 使用 stream 模式，因为部分 API 代理在非流式模式下不返回 content
                    create_kwargs: dict = {
                        "model": current_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True,
                    }
                    if frequency_penalty:
                        create_kwargs["frequency_penalty"] = frequency_penalty
                    if presence_penalty:
                        create_kwargs["presence_penalty"] = presence_penalty

                    stream = await self.client.chat.completions.create(**create_kwargs)
                    chunks: List[str] = []
                    async for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            chunks.append(chunk.choices[0].delta.content)
                    content = "".join(chunks)

                    if model_idx > 0:
                        logger.info(
                            "✅ Fallback 成功: 使用模型 %s 生成, 输出长度=%d",
                            current_model, len(content),
                        )
                    else:
                        logger.info(
                            "LLM 调用成功: model=%s, 输出长度=%d",
                            current_model, len(content),
                        )
                    return content

                except Exception as exc:
                    wait = 2 ** attempt
                    logger.warning(
                        "模型 %s 调用失败 (attempt %d/3): %s, %ds 后重试",
                        current_model, attempt + 1, str(exc)[:100], wait,
                    )
                    await asyncio.sleep(wait)

                    if attempt == 2:  # 第3次重试也失败了
                        all_errors.append((current_model, exc))

        # 所有模型都失败
        error_summary = "; ".join(f"{m}: {str(e)[:50]}" for m, e in all_errors)
        raise RuntimeError(
            f"所有 LLM 模型均失败 (尝试了 {len(models_to_try)} 个模型): {error_summary}"
        ) from all_errors[-1][1]

    async def json_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: Optional[str] = None,
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
