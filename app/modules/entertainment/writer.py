"""娱乐模块 Writer。"""

# ⚠️ 项目第一纲领(不可违背 —— 换任何开发者/维护者/AI 都须第一时间遵循):
#    质量第一,质量低不如不做。本项目的生存前提,是产出"有真实信息增量、
#    读起来不像机器"的高质量内容;宁可少发、不发,也不发低质内容。
#    走质量路线,不走规避路线 —— 目标是"标了 AI 也不掉流量、被检测也不算
#    低质",而非赌平台检测不到。任何为数量/效率/规避而牺牲质量的改动,
#    都违背项目根本目标。详见 README 顶部纲领 与 GUIDE.md §8.3。

import logging
from typing import Optional, Tuple

import markdown as md_lib

from app.services.content_length import count_cn_chars, finalize_article
from app.services.llm.client import LLMClient, get_llm_client
from app.services.prompts import BASE_SYSTEM_PROMPT
from app.services.quality import check_quality

logger = logging.getLogger("autowz.entertainment.writer")

# 娱乐模块专属规则(项目级约束由 BASE_SYSTEM_PROMPT 提供,不在此重复)
ENTERTAINMENT_PROMPT = """
## 模块定位 — 娱乐观察
不做八卦搬运，不造谣，不扒隐私。把一个热门娱乐事件讲清楚：它为什么火、争议在哪、普通观众为什么在意。

## 模块写法要求
- 开头不拘一格——可以用场景、冲突、数据、反问切入，但第一段必须让读者知道在讨论哪部作品/哪个节目/哪件娱乐事件，不能直接空降观点。
- 来源交代方式灵活多样，不要每篇都同一句式。隐含在叙述中即可，不必显式声明"公开信息显示"。
- 第一段要带出看点、悬念、反差或争议。
- 少用财经、政策、宏观经济框架，不要写成财经评论。
- 口语化、有态度、有网感，但不要低俗、不要攻击个人。
- 未经证实的恋情、隐私、爆料，只能写"网传/传闻不可当事实"，不能当真相扩写。
- 禁止编造票房、收视、片酬、恋情、隐私细节。

## 模块推荐结构
1. 抓人开头：一句话点出最大看点或反差。
2. 事件本身：说清作品/人物/节目/争议是什么，第一段就要交代清楚。
3. 看点或争议：为什么大家会讨论。
4. 明确态度：给出判断，不骑墙。
5. 结尾留一个观众视角的问题。
"""


class EntertainmentWriter:
    """娱乐评论写作器。"""

    def __init__(
        self,
        author: str,
        llm_client: Optional[LLMClient] = None,
        *,
        min_chars: int = 600,
        max_chars: int = 800,
        temperature: float = 0.7,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        **_: object,
    ) -> None:
        self.author = author
        self.llm = llm_client or get_llm_client()
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.temperature = temperature
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        # 项目基础约束 + 娱乐模块差异
        self.system_prompt = BASE_SYSTEM_PROMPT.format(
            min_chars=min_chars,
            max_chars=max_chars,
        ) + ENTERTAINMENT_PROMPT

    async def generate(
        self,
        topic: str,
        stance: Optional[str] = None,
        context_text: str = "",
    ) -> dict:
        stance_hint = f"\n立场倾向:{stance}" if stance else ""
        context_block = f"\n\n素材:\n{context_text}" if context_text else ""

        user_prompt = (
            f"话题:{topic}{stance_hint}{context_block}\n\n"
            f"请写一篇娱乐评论，开头自然切入(不要每篇同一句式)，然后展开原创评论→争议分析→明确态度→观众视角结尾。\n\n"
            f"硬性要求:\n"
            f"- 全文{self.min_chars}-{self.max_chars}字\n"
            f"- 第一段让读者知道在讨论哪个事件，但不能直接空降观点\n"
            f"- 开头不拘一格，可以用场景/数据/反差/提问切入，不要每篇都套同一模板\n"
            f"- 严禁出现任何具体媒体名称(新华社/央视/人民日报/中新网/澎湃新闻等),来源用自然方式隐含交代\n"
            f"- 严禁'据X报道'、'X网报道'等转载腔\n"
            f"- 不造谣，不扩写未证实隐私\n"
            f"- 禁止出现素材中没有的具体数字(票房/收视/播放量/片酬/年龄/百分比),没有确切来源就用'多平台''大量''明显'等模糊表述\n"
            f"- 不要财经政治理论腔，不要古文典故\n"
            f"- 每段1-3句，口语化，有态度\n"
            f"- 严禁'我的看法''我的态度''我认为''在我看来'等第一人称表述,用客观第三方视角表态\n"
            f"- 单句不超过80个中文汉字;长句必须拆短,不要无标点长段\n"
            f"- 最后一段必须完整收束,不能半句截断\n"
            f"- 标题12-24字，句式不要套路化:疑问/悬念/反差/直陈中挑最贴切的一种,别每篇都同一个模板,不标题党"
        )

        raw = await self.llm.chat_completion(
            self.system_prompt,
            user_prompt,
            temperature=self.temperature,
            max_tokens=1500,
            frequency_penalty=self.frequency_penalty,
            presence_penalty=self.presence_penalty,
        )

        title, digest, content_md = self._parse_response(raw, topic)
        logger.info("娱乐文本解析成功: topic=%s raw_len=%d", topic, len(raw))

        content_md = finalize_article(content_md, max_chars=self.max_chars)
        content_html = md_lib.markdown(content_md, extensions=["tables"])
        cn_chars = count_cn_chars(content_md)

        if cn_chars < self.min_chars:
            logger.warning(
                "娱乐文章字数偏少: %s (%d字 < %d字)",
                title, cn_chars, self.min_chars,
            )

        logger.info("娱乐文章生成完成: %s (%d字, 最大%d字)", title, cn_chars, self.max_chars)
        quality = check_quality(
            title,
            content_md,
            min_chars=self.min_chars,
            max_chars=self.max_chars,
        )
        if not quality.passed:
            logger.warning(
                "娱乐文章规则质量分偏低: %s score=%s reasons=%s",
                title,
                quality.score,
                "; ".join(quality.reasons),
            )

        return {
            "title": title,
            "digest": digest,
            "content_markdown": content_md,
            "content_html": content_html,
            "style_score": quality.score,
        }

    @staticmethod
    def _parse_response(raw: str, topic: str) -> Tuple[str, str, str]:
        lines = raw.strip().split("\n")
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
                digest = stripped.lstrip(">").strip()
                for prefix in ("摘要:", "摘要：", "摘要 ", "摘要", "概要:", "概要：", "概要"):
                    if digest.startswith(prefix):
                        digest = digest[len(prefix):].strip()
                        break
                body_start = i + 1
                break

        content_md = "\n".join(lines[body_start:]).strip()
        if not title:
            title = topic
        if not digest:
            digest = f"围绕[{topic}]的娱乐观察。"
        if not content_md:
            content_md = raw.strip()
        if len(title) > 64:
            title = title[:62] + "…"
        if len(digest) > 120:
            digest = digest[:118] + "…"
        return title, digest, content_md

