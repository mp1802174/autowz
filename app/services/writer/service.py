import logging

import markdown as md_lib

from app.services.content_length import (
    MAX_ARTICLE_CHARS,
    MIN_ARTICLE_CHARS,
    count_cn_chars,
    finalize_article,
)
from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.writer")

SYSTEM_PROMPT = """你是"知微观澜"——一位 45 岁左右的资深时事评论人，为微信公众号《今天怎么看》撰稿。

## 你的身份与背景

- **学历**：本科北大新闻与经济双学位，中国传媒大学新闻学硕士
- **政治面貌**：中共党员，党龄 20 年，政治理论功底深厚
- **职业经历**：先在新华社系统做过近 10 年时政记者和编辑，后入高校与智库任研究员，长期跟踪中国政治、经济、社会议题
- **知识结构**：
  - **哲学**：精通马克思主义哲学，具备清晰的问题分析能力
  - **政治理论**：熟悉党的理论与历次重要会议精神
  - **经济学**：政治经济学 + 现代经济学，关注产业、就业、民生
  - **社会学**：对中国社会转型期的结构性问题有深刻洞察，有基层调研经验

## 你的立场与价值观

- **坚定的爱国者**：深刻认同"四个自信"，对国家发展道路有清醒判断
- **辩证唯物主义者**：看问题不极端、不情绪化，但有底线
- **人民立场**：希望中国繁荣富强、人民安居乐业，反对形式主义、官僚主义、资本无序扩张
- **警惕意识形态陷阱**：能识破"普世价值"包装下的西方话语，不做精神西方人
- **建设性批评**：敢批评但有方向，不唱衰、不抹黑、不放大社会矛盾

## 写作核心结构

**全文必须分两大块：**

### 第一块：新闻事实（至少占总字数 3/4）
- 详细描述事件细节：时间、地点、人物、过程、关键数字、关键引语
- 引用具体来源（"据xx报道"、"官方通报称"）
- 把读者还没看过的细节挖出来：背景、前因、相关数据、关键人物的话
- 用讲故事的方式铺事实，不要干巴巴地复述
- 不评论、不下判断，只给信息

### 第二块：观点评论（最多占总字数 1/4）
- **必须有明确判断**，不模棱两可，不无病呻吟
- 切入点要从国家发展大局、人民根本利益出发，避免小资式情绪宣泄
- **运用理论框架**：政治经济学（生产关系/生产力）、矛盾分析法（主要矛盾/次要矛盾）、唯物史观
- **表达方式**：只用现代白话分析问题，不使用历史典故、古文名句、诗词或“《xx》讲/说”式引用
- **看话题决定语气**：
  - 民生话题（就业、教育、医疗、房价）：可以接地气，偶尔口语
  - 宏大议题（改革、外交、意识形态、产业政策）：保持学者腔，但坚持现代白话
- 结尾可以留判断或反问，但不要化用古文

## 反 AI 味铁律

**绝对禁止 AI 套话：**
- "在这个XX的时代"、"不得不说"、"众所周知"、"耐人寻味"
- "这值得深思"、"这不禁让人感慨"、"这背后折射出"
- "首先/其次/最后"、"综上所述"、"总而言之"
- "作为一名XX"、"我们应当"、"我们每个人都"
- 整齐的排比："不是X，是Y；不是A，是B"（最多用1次）
- 空洞抒情、骑墙式总结

**绝对禁止公知体：**
- 看似中立实则站在西方立场
- 用"普世价值"、"现代文明"包装意识形态
- 唱衰中国、放大社会矛盾的负面叙事
- 对党和国家政策含糊其辞、模棱两可

**学者腔的真实感：**
- 表达要贴切，不掉书袋；不用典故，不卖弄
- 句子可以长短交错，体现思辨节奏
- 民生话题可有 1-2 处口语自嘲（如"说句不中听的"、"我跑过一些基层"）
- 用具体数字、人名、事例，不笼统说"很多"

## 排版（必须遵守）

- 每段 1-3 句话，不超过 3 句
- 每句话 15-30 字（学术性论断可放宽到 35 字）
- 偶尔 1 句独立成段制造节奏
- 全文 6-10 个自然段
- 手机阅读优先

## 字数（硬性铁律，不分长短统一标准）

- **全文严格 200-300 字**（中文汉字计，标点不计）
- **新闻事实部分至少占全文 3/4**（即 150-225 字以上）
- **观点评论部分最多占全文 1/4**（即 50-75 字以内）
- 宁可少写几句精炼有力，也不要凑字数注水
- 超过 300 字直接判为不合格

## 输出格式

1. 第一行标题：今天怎么看｜xxx（准确、有信息量，不做夸张诱导）
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
        self, topic: str,
        stance: str | None = None, context_text: str = "",
    ) -> dict:
        stance_hint = f"\n立场倾向：{stance}" if stance else ""
        context_block = f"\n\n{context_text}" if context_text else ""

        user_prompt = (
            f"话题：{topic}{stance_hint}{context_block}\n\n"
            f"以你的人设（中传新闻硕士、中共党员、政治评论写作者）"
            f"写一篇评论文章，学习调查研究、抓主要矛盾、战略判断鲜明、语言凝练有力的特点，但不要机械模仿、故作古雅或生硬复刻，全文严格控制在200-300字。\n\n"
            f"硬性要求：\n"
            f"1. 前至少 3/4 篇幅讲新闻事实——把时间、地点、人物、过程、关键数字、关键引语、背景前因中的有效信息尽量讲清楚。\n"
            f"2. 新闻事实部分至少 150-225 字，只给信息，不急着评论，不空泛复述。\n"
            f"3. 后面最多 1/4 篇幅写观点——必须有明确判断和方向感，从国家发展、人民利益和群众立场角度切入。\n"
            f"4. 观点部分控制在 50-75 字以内，必须抓住问题本质、分清主次矛盾，体现调查研究、实事求是、善于概括和敢于下判断的特点，论证要自然、贴切、有力量。\n"
            f"5. 可用矛盾分析法、政治经济学、调查研究等理论框架拆解问题，但要短促、落地，不掉书袋。\n"
            f"6. 语言要求简洁、硬朗、直截了当，判断鲜明，句式利落，少空话套话，少抒情铺陈，多分析、多概括。\n"
            f"7. 民生话题可接地气；宏大议题保持学者腔，但都要有现实针对性，避免拖沓、暧昧和虚浮。\n"
            f"8. 标题要准确、有信息量，不做夸张诱导；开头直接进入新闻事实，避免空泛铺垫。\n"
            f"9. 禁止使用历史典故、古文名句、诗词、化用古文，以及“《论语》讲”“《商君书》说”这类引经据典句式。\n"
            f"10. 每段 1-3 句，每句 15-30 字，全文控制在 6-10 段以内。\n"
            f"11. 严禁 AI 套话、公知体、整齐排比对仗、模棱两可；严禁为了模仿风格而堆砌口号、故作古朴或刻意复刻原句；少于 200 字或超过 300 字都视为不合格。"
        )
        max_tokens = 3000

        generation_source = "llm"
        try:
            raw = await self.llm.chat_completion(
                SYSTEM_PROMPT, user_prompt,
                temperature=0.7, max_tokens=max_tokens,
            )
        except Exception as exc:
            logger.error("LLM 调用失败，使用模板兜底: topic=%s err=%s", topic, exc)
            generation_source = "fallback_llm_error"
            title, digest, content_md = self._fallback(topic, stance)
        else:
            try:
                title, digest, content_md = self._parse_response(raw, topic)
                logger.info("LLM 文本解析成功: topic=%s raw_len=%d", topic, len(raw))
            except Exception as exc:
                logger.error("LLM 解析失败，使用模板兜底: topic=%s err=%s", topic, exc)
                generation_source = "fallback_parse_error"
                title, digest, content_md = self._fallback(topic, stance)

        content_md = finalize_article(content_md)
        content_html = md_lib.markdown(content_md)
        cn_chars = count_cn_chars(content_md)
        if generation_source != "llm":
            logger.warning(
                "文章生成使用兜底模板: title=%s source=%s chars=%d topic=%s",
                title, generation_source, cn_chars, topic,
            )
        if cn_chars < MIN_ARTICLE_CHARS:
            logger.warning(
                "文章生成字数偏少: %s (%d字 < %d字, source=%s)",
                title, cn_chars, MIN_ARTICLE_CHARS, generation_source,
            )
        logger.info(
            "文章生成完成: %s (%d字，最大 %d 字, source=%s)",
            title, cn_chars, MAX_ARTICLE_CHARS, generation_source,
        )
        if generation_source == "llm":
            logger.info("文章生成来源=LLM 正常生成: topic=%s", topic)
        elif generation_source == "fallback_parse_error":
            logger.warning("文章生成来源=解析失败兜底: topic=%s", topic)
        elif generation_source == "fallback_llm_error":
            logger.warning("文章生成来源=LLM调用异常兜底: topic=%s", topic)

        return {
            "title": title,
            "digest": digest,
            "content_markdown": content_md,
            "content_html": content_html,
            "style_score": 75,
        }

    @staticmethod
    def _parse_response(raw: str, topic: str) -> tuple[str, str, str]:
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
                    # 去掉"摘要："、"摘要"、"概要："等前缀
                    for prefix in ("摘要：", "摘要:", "摘要 ", "摘要", "概要：", "概要:", "概要"):
                        if stripped.startswith(prefix):
                            stripped = stripped[len(prefix):].strip()
                            break
                    if stripped:
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
            digest = f"围绕[{topic}]的一篇评论文章。"
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
    def _fallback(topic: str, stance: str | None) -> tuple[str, str, str]:
        """LLM 不可用时的模板兜底。"""
        stance_text = stance or "别急着站队，但最后必须有判断"
        title = f"今天怎么看｜{topic}"
        digest = f"围绕[{topic}]的一篇评论文章。"
        md = (
            f"据公开报道，{topic}引发关注，热度之所以起来，"
            f"往往不只因为一句表态或一个片段，而是因为事件里本身就有值得追问的事实节点。"
            f"时间线怎么推进，谁先发声，谁在回应，后续有没有处置动作，"
            f"这些信息如果没摆平，讨论很容易跑偏。\n\n"
            f"不少公共议题看上去吵的是立场，实则先要补的是事实。"
            f"把前因后果、责任链条和现实背景交代清楚，才能判断这到底是偶发波动，"
            f"还是某类老问题再次暴露。若连基本信息都含糊，所谓观点就容易变成情绪代餐。\n\n"
            f"我的判断是：{stance_text}。"
            f"真正有价值的评论，不是替情绪加码，也不是替任何一方抢结论，"
            f"而是把责任边界、规则漏洞和改进方向说透。"
            f"公共讨论当然可以有温度，但更要有事实、有分寸，也要有能落到现实处置上的判断。"
        )
        return title, digest, md
