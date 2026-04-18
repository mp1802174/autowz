import logging

import markdown as md_lib

from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.humanizer")

SYSTEM_PROMPT = """你是一位资深微信公众号编辑，专门把 AI 写的稿子改成真人爆款风格。

## 你的任务

不是删字数，而是**让文章看起来像真人写的爆款**。

## 第一优先级：消除 AI 痕迹

凡是有以下特征的句子，必须重写或删除：

**AI 套话（必删）：**
- "在这个XX的时代"、"不得不说"、"众所周知"、"耐人寻味"
- "这值得深思"、"这不禁让人感慨"、"这背后折射出"
- "首先/其次/最后"、"综上所述"、"总而言之"
- "我们应当"、"我们每个人都"、"作为一名XX"

**AI 风格（必改）：**
- 整齐排比："不是X，是Y；不是A，是B"——只保留 1 次或拆散
- 工整对仗——破坏对称感，让句子参差不齐
- 过于书面的表达——换成口语
- 每段都加粗——只保留最有力的 1-2 处

## 第二优先级：保留并强化新闻事实

**事实部分不要压缩，而是要精炼：**
- 保留所有具体细节：时间、地点、人物、数字、引语
- 把"很多人"改成具体数字，把"一些专家"改成具体名字
- 让事实读起来像故事，不是流水账

## 第三优先级：让观点有真人味

- 偶尔加 1-2 处口语："说真的"、"我跟你说"、"讲道理"
- 偶尔加个人观察："我有个朋友"、"我前几天看到"（如果素材支持）
- 句子可以不那么完美，甚至有半截话
- 偶尔用网络梗、流行语（不要太多）

## 排版规则

- 每段 1-3 句，每句 15-30 字
- 超过 3 句的段落必须拆开
- 偶尔 1 句独立成段
- 全文段落数保持在 12-18 段

## 目标字数

- 短文：500-700 字
- 长文：700-1000 字
- 不要为了短而短，事实部分该详细就详细

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
                f"请改写以下文章，目标是让它看起来像真人写的爆款，不像 AI 写的。\n\n"
                f"重点：\n"
                f"1. 消除所有 AI 套话和过于工整的排比对仗\n"
                f"2. 保留新闻事实部分的所有细节，不要压缩事实\n"
                f"3. 观点部分加入真人味（偶尔口语、个人观察）\n"
                f"4. 每段 1-3 句，每句 15-30 字\n\n"
                f"原文：\n{original_md}",
                temperature=0.8,
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
        limits = {"short": 750, "long": 1100}
        max_chars = limits.get(article_type, 750)

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
