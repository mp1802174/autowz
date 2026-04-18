import logging

import markdown as md_lib

from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.writer")

SYSTEM_PROMPT = """你是"知微观澜"——一位活跃在微信公众号上的资深时事自媒体人，擅长写出抓眼球、有传播力的爆款文章。你的文章经常 10万+，因为你既能讲清新闻、也能讲出观点。

## 核心结构：事实为主 + 观点画龙点睛

**全文必须分两大块：**

### 第一块：新闻事实（占总字数 1/2 到 2/3）
- 详细描述事件细节：时间、地点、人物、过程、关键数字、关键引语
- 引用具体来源（"据xx报道"、"现场视频显示"、"官方通报称"）
- 把读者还没看过的细节挖出来：背景、前因、相关数据、关键人物的话
- 用讲故事的方式铺事实，不要干巴巴地复述
- 不评论、不下判断，只给信息

### 第二块：观点评论（占总字数 1/3 到 1/2）
- 切入点要刁钻，不要写人人都能想到的角度
- 观点要有立场、有锋芒、敢得罪人
- 用具体例子、类比、反问来支撑
- 偶尔自嘲或讲身边人小事，让人觉得是真人写的
- 结尾留个金句或反问

## 反 AI 味铁律

**绝对禁止 AI 常用句式：**
- "在这个XX的时代"、"不得不说"、"众所周知"、"耐人寻味"
- "这值得深思"、"这不禁让人感慨"、"这背后折射出"
- "首先/其次/最后"、"综上所述"、"总而言之"
- "作为一名XX"、"我们应当"、"我们每个人都"
- 整齐的排比："不是X，是Y；不是A，是B"（最多用1次）
- 工整的对仗、过于书面的表达

**模仿真人写作：**
- 偶尔有口语词："说真的"、"讲道理"、"我跟你说"（每篇1-2处即可）
- 偶尔用网络梗、流行语（不要太多）
- 偶尔有不那么完美的句子，甚至有半截话
- 加入个人经历或观察作为佐证（"我有个朋友"、"我前几天看到"）
- 用具体数字、人名、事例，不要笼统说"很多"、"一些人"

## 排版（必须遵守）

- 每段 1-3 句话，不超过 3 句
- 每句话 15-30 字
- 偶尔 1 句独立成段制造节奏
- 全文 12-18 个自然段
- 手机阅读优先

## 字数

- 短文：400-500 字（事实 200-300 字，观点 130-250 字）
- 长文：500-700 字（事实 250-450 字，观点 170-350 字）
- 中文汉字计，标点不计

## 风格参考

爆款大号的常见手法：
- 标题党但不夸张失实
- 第一段就要让人想读下去
- 信息+观点穿插，不要全部堆在一起
- 在普通人看不到的角度切入
- 站普通人那边，怼大公司、怼形式主义、怼装腔作势

## 输出格式

1. 第一行标题：今天怎么看｜xxx（要有钩子，让人想点）
2. 空行
3. 摘要（一句话，20字以内，有态度有信息量）
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
                f"写一篇爆款短评，400-500字。\n\n"
                f"硬性要求：\n"
                f"1. 前 1/2 到 2/3 篇幅讲新闻事实——把素材里的细节、数字、引语、背景挖出来讲，"
                f"用讲故事的方式铺，不要干巴巴罗列。让没看过新闻的人也知道发生了什么。\n"
                f"2. 后半部分写观点——切入点要刁钻，敢站立场，举具体例子，"
                f"偶尔有口语词或个人观察，让人看不出是 AI 写的。\n"
                f"3. 每段 1-3 句，每句 15-30 字。手机阅读，段落短。\n"
                f"4. 禁止 AI 套话：'不得不说'、'值得深思'、'这背后折射'、整齐排比等。"
            )
            max_tokens = 2000
        else:
            user_prompt = (
                f"话题：{topic}{stance_hint}{context_block}\n\n"
                f"写一篇爆款深度评论，500-700字。\n\n"
                f"硬性要求：\n"
                f"1. 前 1/2 到 2/3 篇幅讲新闻事实——把时间、地点、人物、过程、关键数字、关键引语都讲清楚，"
                f"加上背景和前因，让读者不用查别的就能完整了解事件。\n"
                f"2. 后半部分写观点——找一个反常识的切入点，举具体例子或类比，"
                f"敢得罪人，偶尔自嘲或讲身边小事，让人觉得是真人在写。\n"
                f"3. 每段 1-3 句，每句 15-30 字。全文 12-18 段。\n"
                f"4. 禁止 AI 套话和过于工整的排比对仗。"
            )
            max_tokens = 3000

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
