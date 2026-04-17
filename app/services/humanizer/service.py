import logging

import markdown as md_lib

from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.humanizer")

SYSTEM_PROMPT = """你是一位资深微信公众号编辑，你的核心任务是**激进压缩、提纯信息**。

## 第一优先级：删到极致

逐句审查，遇到以下情况直接删除或合并：
- 同一个意思说了两遍（哪怕换了说法）→ 只保留更有力的那句
- 空洞感慨（"这值得深思"、"不禁让人感慨"、"这背后的原因耐人寻味"）→ 删
- 万能过渡（"不得不说"、"众所周知"、"在这个XX的时代"）→ 删
- 没有信息增量的铺垫句 → 删
- 冗余修饰词（"非常"、"十分"、"极其"、"相当"）→ 删
- 能用5个字说清楚的，绝不用10个字

## 第二优先级：压缩表述

- 每句话控制在15-30字
- 超过3句的段落拆开，每段1-3句
- 连接词（然而/但是/因此）能删就删，用换行替代
- 模板化开头（连续两段结构相似）→ 重写一段
- 偶尔1句话成段制造节奏，但不要每段都这样

## 不要做的事

- 不要加新观点或新论据
- 不要扩写，只能保持或缩短
- 不要加口语标记（"说白了"等）超过2处
- 不要每段都加粗

## 目标

改写后的字数应该是原文的 60-70%。如果原文 800 字，改写后应该在 480-560 字。

## 输出

只输出改写后的正文（Markdown），不要标题、摘要或任何说明。
"""


class HumanizerService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or get_llm_client()

    async def rewrite(self, draft: dict) -> dict:
        original_md = draft["content_markdown"]

        try:
            rewritten_md = await self.llm.chat_completion(
                SYSTEM_PROMPT,
                f"请激进压缩以下文章。核心任务：删掉一切废话和重复论证，"
                f"压缩冗余表述，让每句话都精炼有力。每句控制在15-30字。"
                f"目标：改写后字数为原文的60-70%。\n\n{original_md}",
                temperature=0.7,
                max_tokens=4096,
            )
            rewritten_md = rewritten_md.strip()
            if len(rewritten_md) < len(original_md) * 0.3:
                logger.warning("改写结果过短，使用原文")
                rewritten_md = original_md
                style_score = draft.get("style_score", 70)
            else:
                style_score = min(100, draft.get("style_score", 70) + 15)
        except Exception as exc:
            logger.error("LLM 改写失败，使用原文: %s", exc)
            rewritten_md = original_md
            style_score = draft.get("style_score", 70)

        rewritten_md = self._trim_to_limit(rewritten_md, draft.get("_article_type", "short"))
        content_html = md_lib.markdown(rewritten_md)
        logger.info("人味化改写完成, style_score=%d", style_score)

        return {
            **draft,
            "content_markdown": rewritten_md,
            "content_html": content_html,
            "style_score": style_score,
        }

    @staticmethod
    def _split_long_paragraphs(text: str, max_sentences: int = 3) -> str:
        """把超过 max_sentences 句的段落自动拆分，适配手机阅读。"""
        import re

        # 中文句子结束标志：句号、问号、感叹号、省略号
        sentence_end = re.compile(r'([。？！…]+["」）)]*)')

        lines = text.split("\n")
        result: list[str] = []

        for line in lines:
            stripped = line.strip()
            # 空行、标题行、加粗行直接保留
            if not stripped or stripped.startswith("#") or stripped.startswith("**"):
                result.append(line)
                continue

            # 按句子切分
            parts = sentence_end.split(stripped)
            # 重新组合：把标点黏回句子
            sentences: list[str] = []
            buf = ""
            for part in parts:
                buf += part
                if sentence_end.match(part):
                    sentences.append(buf)
                    buf = ""
            if buf.strip():
                sentences.append(buf)

            if len(sentences) <= max_sentences:
                result.append(line)
                continue

            # 拆分：每 2-3 句一段
            chunk: list[str] = []
            for i, s in enumerate(sentences):
                chunk.append(s)
                # 每 2 句拆一次，但如果下一句很短（<15字）则多带一句
                if len(chunk) >= 2:
                    remaining = len(sentences) - i - 1
                    next_short = (
                        i + 1 < len(sentences)
                        and len(sentences[i + 1].strip()) < 15
                    )
                    if len(chunk) >= max_sentences or (not next_short and remaining > 0):
                        result.append("".join(chunk).strip())
                        result.append("")  # 空行分段
                        chunk = []
            if chunk:
                result.append("".join(chunk).strip())

        # 清理多余空行
        cleaned: list[str] = []
        for line in result:
            if line.strip() == "" and cleaned and cleaned[-1].strip() == "":
                continue
            cleaned.append(line)

        return "\n".join(cleaned).strip()

    @staticmethod
    def _trim_to_limit(text: str, article_type: str) -> str:
        """如果中文字数超标，从末尾按段落裁剪（保留最后一段作为结尾）。"""
        limits = {"short": 600, "long": 850}
        max_chars = limits.get(article_type, 600)

        cn_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if cn_count <= max_chars:
            return text

        # 按空行或单换行分段
        import re
        paragraphs = re.split(r'\n\s*\n|\n(?=\*\*)', text)
        if len(paragraphs) <= 2:
            # 按单换行拆
            paragraphs = [p for p in text.split("\n") if p.strip()]

        if len(paragraphs) <= 2:
            return text

        sep = "\n\n"
        # 保留结尾段，从倒数第二段开始删
        ending = paragraphs[-1]
        body = paragraphs[:-1]

        while len(body) > 1:
            candidate = sep.join(body) + sep + ending
            cn = sum(1 for c in candidate if '\u4e00' <= c <= '\u9fff')
            if cn <= max_chars:
                return candidate
            body.pop(-1)

        return sep.join(body) + sep + ending
