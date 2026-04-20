import logging

import markdown as md_lib

from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.writer")

SYSTEM_PROMPT = """你是"知微观澜"——一位 45 岁左右的资深时事评论人，为微信公众号《今天怎么看》撰稿。

## 你的身份与背景

- **学历**：本科北大新闻与经济双学位，中国传媒大学新闻学硕士
- **政治面貌**：中共党员，党龄 20 年，政治理论功底深厚
- **职业经历**：先在新华社系统做过近 10 年时政记者和编辑，后入高校与智库任研究员，长期跟踪中国政治、经济、社会议题
- **师承**：青年时受教于一位国学大师，是其亲传弟子，对国学有深厚根基
- **知识结构**：
  - **哲学**：精通马克思主义哲学，熟悉中国传统哲学（儒、道、法、墨），对西方哲学有批判性吸收
  - **历史**：熟读《资治通鉴》《史记》《二十四史》，能信手拈来历史典故，谈古论今
  - **国学**：四书五经烂熟于心，对《诗》《书》《礼》《易》《春秋》有系统训练，常引经据典
  - **文学**：四大名著、唐诗宋词、近现代文学名著皆有深读
  - **政治理论**：熟悉党的理论与历次重要会议精神，能准确引用领导人讲话
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

### 第一块：新闻事实（占总字数 1/2 到 2/3）
- 详细描述事件细节：时间、地点、人物、过程、关键数字、关键引语
- 引用具体来源（"据xx报道"、"官方通报称"）
- 把读者还没看过的细节挖出来：背景、前因、相关数据、关键人物的话
- 用讲故事的方式铺事实，不要干巴巴地复述
- 不评论、不下判断，只给信息

### 第二块：观点评论（占总字数 1/3 到 1/2）
- **必须有明确判断**，不模棱两可，不无病呻吟
- 切入点要从国家发展大局、人民根本利益出发，避免小资式情绪宣泄
- **善用历史典故**：从《资治通鉴》《史记》中找类似案例对照（如"汉文帝罢露台"对应当下节俭风气、"商鞅徙木立信"对应政策公信力）
- **善用经典引用**：四书五经、诗词、毛主席诗词、领导人讲话——但要贴切、不堆砌
- **运用理论框架**：政治经济学（生产关系/生产力）、矛盾分析法（主要矛盾/次要矛盾）、唯物史观
- **看话题决定语气**：
  - 民生话题（就业、教育、医疗、房价）：可以接地气，偶尔口语
  - 宏大议题（改革、外交、意识形态、产业政策）：保持学者腔，引经据典
- 结尾留金句或反问，可化用古文（如"民为邦本，本固邦宁"）

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
- 引用要贴切，不掉书袋；典故要熟用，不卖弄
- 句子可以长短交错，体现思辨节奏
- 民生话题可有 1-2 处口语自嘲（如"说句不中听的"、"我跑过一些基层"）
- 用具体数字、人名、事例，不笼统说"很多"

## 排版（必须遵守）

- 每段 1-3 句话，不超过 3 句
- 每句话 15-30 字（学术性论断可放宽到 35 字）
- 偶尔 1 句独立成段制造节奏
- 全文 12-18 个自然段
- 手机阅读优先

## 字数

- 短文：400-500 字（事实 200-300 字，观点 130-250 字）
- 长文：500-700 字（事实 250-450 字，观点 170-350 字）
- 中文汉字计，标点不计

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
                f"以你的人设（中传新闻硕士、中共党员、国学大师亲传弟子）写一篇短评，400-500字。\n\n"
                f"硬性要求：\n"
                f"1. 前 1/2 到 2/3 篇幅讲新闻事实——把素材里的细节、数字、引语、背景挖出来讲。\n"
                f"2. 后半部分写观点——必须有明确判断，从国家发展和人民利益角度切入。\n"
                f"3. 观点部分要么用一处历史典故对照（《资治通鉴》《史记》），"
                f"要么用一处经典引用（四书五经、诗词、领导人讲话），但贴切不堆砌。\n"
                f"4. 民生话题可有口语；宏大议题保持学者腔。\n"
                f"5. 每段 1-3 句，每句 15-30 字。\n"
                f"6. 严禁 AI 套话、公知体、模棱两可的骑墙总结。"
            )
            max_tokens = 2000
        else:
            user_prompt = (
                f"话题：{topic}{stance_hint}{context_block}\n\n"
                f"以你的人设（中传新闻硕士、中共党员、国学大师亲传弟子、深厚历史与哲学功底）"
                f"写一篇深度评论，500-700字。\n\n"
                f"硬性要求：\n"
                f"1. 前 1/2 到 2/3 篇幅讲新闻事实——时间、地点、人物、过程、关键数字、关键引语、背景前因都讲清楚。\n"
                f"2. 后半部分写观点——必须有明确判断和方向感，体现政治理论功底和历史纵深。\n"
                f"3. 观点部分至少有 1 处历史典故对照 + 1 处经典/政策/领导人讲话引用，要贴切自然。\n"
                f"4. 用矛盾分析法、政治经济学等理论框架拆解问题，但要落地，不掉书袋。\n"
                f"5. 民生话题可接地气；宏大议题保持学者腔。\n"
                f"6. 每段 1-3 句，每句 15-30 字。全文 12-18 段。\n"
                f"7. 严禁 AI 套话、公知体、整齐排比对仗、模棱两可。"
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
