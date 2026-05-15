import logging

import markdown as md_lib

from app.services.content_length import (
    MAX_ARTICLE_CHARS,
    MIN_ARTICLE_CHARS,
    count_cn_chars,
    finalize_article,
)
from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.humanizer")

SYSTEM_PROMPT = """你是一位资深政论编辑，负责把稿件润色为符合"知微观澜"主笔人设的成稿。

## 主笔人设（你必须维护的腔调）

主笔是 45 岁的资深时评人：中传新闻硕士、中共党员。
- 政治立场坚定，深谙马克思主义哲学和党的理论
- 写文章既有理论纵深，又能讲清事实
- 站在国家发展大局和人民利益立场，反对公知体、反对无病呻吟

## 你的任务

不是简单删字数，而是**让文章读起来像这位主笔亲笔所写**。

## 第一优先级：消除 AI 痕迹

**AI 套话必删：**
- "在这个XX的时代"、"不得不说"、"众所周知"、"耐人寻味"
- "这值得深思"、"这不禁让人感慨"、"这背后折射出"
- "首先/其次/最后"、"综上所述"、"总而言之"
- "我们应当"、"我们每个人都"

**AI 风格必改：**
- 整齐排比、工整对仗——破坏对称感
- 过度修饰、空洞抒情——删
- 每段都加粗——只保留最有力的 1-2 处

**公知体必改：**
- 看似中立实则站西方立场——重写，回归人民立场
- 模棱两可的骑墙式总结——必须给出明确判断
- 用"普世价值"包装意识形态——剥掉伪装

## 第二优先级：强化人设特征

**保留并强化以下要素（如果原文有）：**
- 理论框架（矛盾分析法、政治经济学概念）
- 明确的立场判断

**禁止主动补充历史典故、古文名句、四书五经、诗词或“《xx》讲/说”式引用。**

## 第三优先级：保留新闻事实

事实部分不要压缩，保留所有具体细节：时间、地点、人物、数字、引语。
让事实读起来像故事，不是流水账。

## 第四优先级：控制事实与观点比例

- 新闻事实至少保留全文 3/4，优先保留时间、地点、人物、数字、引语、背景前因
- 观点评论最多占全文 1/4，只保留最核心判断
- 开头直接进入新闻事实，避免空泛铺垫
- 结尾可以有判断，但不要写关注、点赞、转发、求回复等转化话术

## 语气分寸

- **民生话题**（就业、教育、医疗、房价）：可有 1-2 处口语表达（"说句不中听的"等）
- **宏大议题**（改革、外交、产业政策）：保持学者腔，但用现代白话表达，不引经据典

## 排版规则

- 每段 1-3 句，每句 15-30 字（学术性论断可放宽到 35 字）
- 超过 3 句的段落必须拆开
- 偶尔 1 句独立成段
- 全文段落数保持在 6-10 段

## 目标字数

- 不分长短，全文统一严格控制在 200-300 字
- 新闻事实部分至少占全文 3/4，约 150-225 字以上
- 观点评论部分最多占全文 1/4，约 50-75 字以内
- 事实部分要尽量完整，优先压缩观点而不是压缩事实

## 输出

只输出改写后的正文（Markdown），不要标题、摘要或任何说明。
"""


class HumanizerService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or get_llm_client()

    async def rewrite(self, draft: dict) -> dict:
        original_md = draft["content_markdown"]
        original_chars = count_cn_chars(original_md)

        try:
            rewritten_md = await self.llm.chat_completion(
                SYSTEM_PROMPT,
                f"请把以下文章润色成符合主笔人设（中传新闻硕士、中共党员）的成稿。\n\n"
                f"重点：\n"
                f"1. 消除所有 AI 套话、公知体、模棱两可的骑墙总结\n"
                f"2. 保留新闻事实部分的所有细节\n"
                f"3. 观点部分只允许使用现代白话和理论分析，禁止补充历史典故、古文名句、诗词或“《xx》讲/说”式引用\n"
                f"4. 民生话题可有口语；宏大议题保持学者腔，但不用引经据典\n"
                f"5. 新闻事实至少占全文 3/4，优先保留具体事实细节；观点评论最多占全文 1/4，只保留最核心判断\n"
                f"6. 不写关注、点赞、转发、求回复等转化话术，结尾不要硬做互动引导\n"
                f"7. 每段 1-3 句，每句 15-30 字\n"
                f"8. 全文严格控制在 200-300 字，新闻事实部分至少 3/4，观点评论最多 1/4\n\n"
                f"原文：\n{original_md}",
                temperature=0.8,
                max_tokens=4096,
            )
            rewritten_md = rewritten_md.strip()
            rewritten_chars = count_cn_chars(rewritten_md)
            if len(rewritten_md) < len(original_md) * 0.3 or rewritten_chars < MIN_ARTICLE_CHARS:
                if original_chars < MIN_ARTICLE_CHARS:
                    logger.warning(
                        "改写结果过短且原文也偏短，转入补足改写: rewritten=%d original=%d min=%d",
                        rewritten_chars, original_chars, MIN_ARTICLE_CHARS,
                    )
                    rewritten_md = await self._expand_short_article(original_md)
                    rewritten_chars = count_cn_chars(rewritten_md)
                    if rewritten_chars < MIN_ARTICLE_CHARS:
                        logger.warning(
                            "补足改写仍过短，使用保底扩写模板: rewritten=%d original=%d",
                            rewritten_chars, original_chars,
                        )
                        rewritten_md = self._fallback_expand_short_article(original_md)
                        rewritten_chars = count_cn_chars(rewritten_md)
                        if rewritten_chars < MIN_ARTICLE_CHARS:
                            logger.warning("保底扩写仍过短，使用原文: rewritten=%d original=%d", rewritten_chars, original_chars)
                            rewritten_md = original_md
                            style_score = draft.get("style_score", 70)
                        else:
                            style_score = min(100, draft.get("style_score", 70) + 10)
                    else:
                        style_score = min(100, draft.get("style_score", 70) + 15)
                else:
                    logger.warning("改写结果过短，使用原文: rewritten=%d original=%d", rewritten_chars, original_chars)
                    rewritten_md = original_md
                    style_score = draft.get("style_score", 70)
            else:
                style_score = min(100, draft.get("style_score", 70) + 15)
        except Exception as exc:
            logger.error("LLM 改写失败，使用原文: %s", exc)
            rewritten_md = original_md
            style_score = draft.get("style_score", 70)

        rewritten_md = self._trim_to_limit(rewritten_md)
        content_html = md_lib.markdown(rewritten_md)
        logger.info("人味化改写完成, style_score=%d", style_score)

        return {
            **draft,
            "content_markdown": rewritten_md,
            "content_html": content_html,
            "style_score": style_score,
        }

    async def _expand_short_article(self, original_md: str) -> str:
        rewritten_md = await self.llm.chat_completion(
            SYSTEM_PROMPT,
            f"下面这篇稿子已经有基本框架，但字数不足。请在不改变核心事实和判断的前提下，"
            f"补足细节与分析，把全文扩写到 200-300 字。\n\n"
            f"硬性要求：\n"
            f"1. 保留原文已有事实、判断和段落节奏，不要另起炉灶\n"
            f"2. 优先补足事实细节、背景交代和观点论证，不要空话套话\n"
            f"3. 禁止引经据典，禁止古文腔，禁止新增无根据事实\n"
            f"4. 全文必须达到 200-300 字\n\n"
            f"原文：\n{original_md}",
            temperature=0.8,
            max_tokens=4096,
        )
        return rewritten_md.strip()

    @staticmethod
    def _fallback_expand_short_article(original_md: str) -> str:
        body = (
            f"{original_md.strip()}\n\n"
            f"如果只停在眼前情绪，这类讨论往往走不远。"
            f"把事实补齐，把责任边界讲明，把后续处置放到规则框架里看，"
            f"结论才有分量。\n\n"
            f"说到底，公共讨论不是谁声音大谁就占理。"
            f"真正值得盯住的，是信息有没有遗漏，回应是否及时，"
            f"以及类似问题还会不会重复出现。"
        )
        return body.strip()

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
    def _trim_to_limit(text: str) -> str:
        """如果中文字数超标，先裁正文，再追加字数括号。"""
        return finalize_article(text, MAX_ARTICLE_CHARS)
