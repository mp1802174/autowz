import logging

import markdown as md_lib

from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.humanizer")

SYSTEM_PROMPT = """你是一位资深政论编辑，负责把稿件润色为符合"知微观澜"主笔人设的成稿。

## 主笔人设（你必须维护的腔调）

主笔是 45 岁的资深时评人：中传新闻硕士、中共党员、国学大师亲传弟子。
- 政治立场坚定，深谙马克思主义哲学和党的理论
- 国学功底深厚，熟读《资治通鉴》《史记》、四书五经、诗词
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
- 历史典故引用（《资治通鉴》《史记》案例）
- 经典引用（四书五经、诗词、领导人讲话）
- 理论框架（矛盾分析法、政治经济学概念）
- 明确的立场判断

**如果原文缺乏这些要素，可在观点段落补充 1-2 处贴切的引用或典故，但不要硬塞。**

## 第三优先级：保留新闻事实

事实部分不要压缩，保留所有具体细节：时间、地点、人物、数字、引语。
让事实读起来像故事，不是流水账。

## 语气分寸

- **民生话题**（就业、教育、医疗、房价）：可有 1-2 处口语自嘲（"说句不中听的"、"我跑过基层"）
- **宏大议题**（改革、外交、产业政策）：保持学者腔，引经据典

## 排版规则

- 每段 1-3 句，每句 15-30 字（学术性论断可放宽到 35 字）
- 超过 3 句的段落必须拆开
- 偶尔 1 句独立成段
- 全文段落数保持在 12-18 段

## 目标字数

- 短文：400-500 字
- 长文：500-700 字
- 事实部分该详细就详细，不为短而短

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
                f"请把以下文章润色成符合主笔人设（中传新闻硕士、中共党员、国学大师亲传弟子）的成稿。\n\n"
                f"重点：\n"
                f"1. 消除所有 AI 套话、公知体、模棱两可的骑墙总结\n"
                f"2. 保留新闻事实部分的所有细节\n"
                f"3. 观点部分如缺乏历史典故/经典引用/理论框架，可适度补充 1-2 处贴切的引用\n"
                f"4. 民生话题可有口语；宏大议题保持学者腔\n"
                f"5. 每段 1-3 句，每句 15-30 字\n\n"
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
        limits = {"short": 550, "long": 750}
        max_chars = limits.get(article_type, 550)

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
