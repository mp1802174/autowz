import logging

import markdown as md_lib

from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.writer")

SYSTEM_PROMPT = """你是"知微观澜"——一位毒舌、犀利的时事评论人，为微信公众号《今天怎么看》撰稿。你的风格接近许知远式的知识分子锐评，而非新闻联播播音腔。

## 铁律：信息密度 + 极致精炼

每一句话都必须提供新信息或新角度。写完一句，问自己"删掉这句读者会少知道什么？"——如果答案是"什么也不少"，就删掉它。

**更重要的是：能用5个字说清楚的，绝不用10个字。**

绝对禁止：
- 车轱辘话：同一个意思换个说法再说一遍
- 空洞抒情："这值得我们每一个人深思"、"这不禁让人感慨"
- 万能句式："在这个XX的时代"、"不得不说"、"众所周知"
- 序列词："首先/其次/最后/第一/第二/第三/综上所述/总而言之"
- 暴露AI："作为一名AI"或任何类似表述
- 冗余修饰：删掉所有不影响意思的形容词和副词

## 结构

1. **开头**（1-2段）：直接交代事件核心事实——谁、做了什么、什么结果。引用素材来源。不铺垫、不渲染。每段2句话以内。
2. **中段**：你的分析和判断。不要列分论点编号，用自然行文推进。每段只说一件事，说完就走，不回头。关键判断可以用**加粗短句**强调。每段2-3句话，每句话15-25字。
3. **结尾**（1段）：金句收尾或反问留白。不总结、不复述。1-2句话。

## 排版

- 每段1-3句话，不超过3句
- 每句话控制在15-30字之间
- 偶尔1句话独立成段制造节奏感
- 全文10-15个自然段
- 手机阅读优先，段落越短越好

## 风格

- 像一个聪明的朋友跟你掰扯——有判断、有证据、有态度
- 先亮观点，再摆事实，不要先铺垫一堆背景
- 口语过渡自然穿插，但不要每段都用，显得油
- 敢站队，但不是抬杠，要有论据支撑
- 基于素材写，不编造细节

## 字数

- 短文：400-550字（宁短勿水，写到400字观点说完了就收）
- 长文：550-800字
- 中文汉字计，标点不计

## 输出格式

1. 第一行标题：今天怎么看｜xxx
2. 空行
3. 摘要（一句话，20字以内，要有态度）
4. 空行
5. 正文（Markdown）
"""


class WriterService:
    def __init__(self, author: str, llm_client: LLMClient | None = None) -> None:
        self.author = author
        self.llm = llm_client or get_llm_client()

    async def generate(
        self, topic: str, article_type: str,
        stance: str | None = None, context_text: str = "",
    ) -> dict:
        stance_hint = f"\n立场倾向：{stance}" if stance else ""
        context_block = f"\n\n{context_text}" if context_text else ""

        if article_type == "short":
            user_prompt = (
                f"话题：{topic}{stance_hint}{context_block}\n\n"
                f"写一篇冲突型短评，400-550字。\n"
                f"要求：直接亮观点，不铺垫。每句话15-30字，信息密度要高。"
                f"说完就走不回头。禁止翻来覆去论证同一个点。"
            )
            max_tokens = 1800
        else:
            user_prompt = (
                f"话题：{topic}{stance_hint}{context_block}\n\n"
                f"写一篇深度评论，550-800字。\n"
                f"要求：开头交代事实，中段分析背后逻辑（不要列编号），"
                f"结尾金句收。每句话15-30字，每句都要有新信息，禁止车轱辘话。"
            )
            max_tokens = 4000

        try:
            raw = await self.llm.chat_completion(
                SYSTEM_PROMPT, user_prompt,
                temperature=0.7, max_tokens=max_tokens,
            )
            title, digest, content_md = self._parse_response(raw, topic, article_type)
        except Exception as exc:
            logger.error("LLM 生成失败，使用模板兜底: %s", exc)
            title, digest, content_md = self._fallback(topic, article_type, stance)

        content_html = md_lib.markdown(content_md)
        logger.info("文章生成完成: %s (%d字)", title, len(content_md))

        return {
            "title": title,
            "digest": digest,
            "content_markdown": content_md,
            "content_html": content_html,
            "style_score": 75,
            "_article_type": article_type,
        }

    @staticmethod
    def _parse_response(raw: str, topic: str, article_type: str) -> tuple[str, str, str]:
        """解析 LLM 输出，提取标题、摘要、正文。

        DeepSeek 等模型有时会在文章前输出思维过程，
        所以需要找到"今天怎么看"标题行作为文章的真正起点。
        """
        lines = raw.strip().split("\n")

        # 先尝试找"今天怎么看"标题行
        title_line_idx = -1
        for i, line in enumerate(lines):
            stripped = line.strip().lstrip("#").strip()
            if "今天怎么看" in stripped:
                title_line_idx = i
                break

        if title_line_idx >= 0:
            # 从标题行开始解析
            title = lines[title_line_idx].strip().lstrip("#").strip()
            digest = ""
            body_start = title_line_idx + 1
            for i in range(title_line_idx + 1, len(lines)):
                stripped = lines[i].strip()
                if not stripped:
                    continue
                if not digest:
                    digest = stripped
                    body_start = i + 1
                    break
        else:
            # 没找到标记，取第一个非空行作为标题
            title = ""
            digest = ""
            body_start = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                if not title:
                    title = stripped.lstrip("#").strip()
                    continue
                if not digest:
                    digest = stripped
                    body_start = i + 1
                    break

        content_md = "\n".join(lines[body_start:]).strip()

        if not title:
            title = f"今天怎么看｜{topic}"
        if not digest:
            digest = f"围绕[{topic}]的一篇{'短评' if article_type == 'short' else '深度评论'}。"
        if not content_md:
            content_md = raw.strip()

        # 微信标题限制 64 字符
        if len(title) > 64:
            title = title[:62] + "…"

        # 微信摘要限制 120 字符
        if len(digest) > 120:
            digest = digest[:118] + "…"

        return title, digest, content_md

    @staticmethod
    def _fallback(topic: str, article_type: str, stance: str | None) -> tuple[str, str, str]:
        """LLM 不可用时的模板兜底。"""
        stance_text = stance or "别急着站队，但最后必须有判断"
        title = f"今天怎么看｜{topic}"
        digest = f"围绕[{topic}]的一篇{'短评' if article_type == 'short' else '深度评论'}。"
        if article_type == "short":
            md = (
                f"**我的判断先摆在前面：这事不能只看表面。**\n\n"
                f"{topic}之所以能冲上热度，不是因为大家真的关心事实，"
                f"而是每个人都想把自己的情绪塞进去。\n\n"
                f"一种看法觉得这就是老问题的新版本，没什么可大惊小怪；"
                f"另一种看法则觉得，正因为它又一次发生，才更该较真。\n\n"
                f"我更偏向后者。{stance_text}。"
                f"如果一件事总被当成谈资，它就永远进不了真正的公共讨论。"
            )
        else:
            md = (
                f"**先说结论：{topic}不是一个孤立新闻，它更像一面镜子。**\n\n"
                f"先看事件本身，它为什么会在今天爆开；"
                f"再看围观者心理，为什么大家总爱把复杂问题简化成立场对撞。\n\n"
                f"支持者看到的是效率、情绪或者公平；"
                f"反对者看到的是代价、失衡或者后果。\n\n"
                f"我的态度是：{stance_text}。"
                f"真正有价值的评论，不是替谁喊口号，"
                f"而是告诉读者这件事以后还会怎样演化。"
            )
        return title, digest, md
