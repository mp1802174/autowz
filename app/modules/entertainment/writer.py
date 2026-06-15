"""娱乐模块 Writer。"""

import logging

import markdown as md_lib

from app.services.content_length import count_cn_chars, finalize_article
from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.entertainment.writer")

SYSTEM_PROMPT_TEMPLATE = """你是《现象观察》的娱乐观察作者，给微信公众号写热门影视、明星、综艺、文娱事件评论。

## 核心定位
不做八卦搬运，不造谣，不扒隐私。把一个热门娱乐事件讲清楚：它为什么火、争议在哪、普通观众为什么在意。

## 写法要求
- 第一段必须先交代"事实式来源 + 事件事实 + 看点/争议"。
- 可用表达:"公开信息显示""平台数据显示""从目前公开资料看""猫眼/灯塔等平台数据显示"。
- 开头不能直接空降观点,必须让读者知道是哪部作品/哪个节目/哪件娱乐事件。
- 第一段要带出看点、悬念、反差或争议。
- 禁止用“据X报道”“根据X报道”“X网报道”“近日消息称”开头。
- 正文也要少用转载稿口吻；需要交代来源时，改成“公开信息显示”“相关材料显示”。
- 少用财经、政策、宏观经济框架，不要写成财经评论。
- 口语化、有态度、有网感，但不要低俗、不要攻击个人。
- 未经证实的恋情、隐私、爆料，只能写“网传/传闻不可当事实”，不能当真相扩写。
- 每段1-3句，节奏快。

## 推荐结构
1. 抓人开头：一句话点出最大看点或反差。
2. 事件本身：说清作品/人物/节目/争议是什么，第一段就要交代清楚。
3. 看点或争议：为什么大家会讨论。
4. 明确态度：给出判断，不骑墙。
5. 结尾留一个观众视角的问题。

## 严格禁止
- AI套话：“值得深思”“引发广泛关注”“在这个时代”“不得不说”。
- 古文典故和过度拔高。
- 财经政治理论框架。
- 关注、点赞、转发引导。
- 编造票房、收视、片酬、恋情、隐私细节。

## 字数控制
- 全文严格{min_chars}-{max_chars}字，中文汉字计数，标点不计。

## 输出格式
只输出：
1. 第一行：标题，12-24字，有看点但不标题党。
2. 空行
3. 摘要，一句话，20字以内。
4. 空行
5. 正文，Markdown格式。

不要输出说明、思考过程、字数统计。
"""


class EntertainmentWriter:
    """娱乐评论写作器。"""

    def __init__(
        self,
        author: str,
        llm_client: LLMClient | None = None,
        *,
        min_chars: int = 650,
        max_chars: int = 800,
        temperature: float = 0.7,
        **_: object,
    ) -> None:
        self.author = author
        self.llm = llm_client or get_llm_client()
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.temperature = temperature
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            min_chars=min_chars,
            max_chars=max_chars,
        )

    async def generate(
        self,
        topic: str,
        stance: str | None = None,
        context_text: str = "",
    ) -> dict:
        stance_hint = f"\n立场倾向:{stance}" if stance else ""
        context_block = f"\n\n素材:\n{context_text}" if context_text else ""

        user_prompt = (
            f"话题:{topic}{stance_hint}{context_block}\n\n"
            f"请写一篇娱乐评论，结构按：事实式来源+事件事实+看点→原创评论→争议分析→明确态度→观众视角结尾。\n\n"
            f"硬性要求:\n"
            f"- 全文{self.min_chars}-{self.max_chars}字\n"
            f"- 第一段必须交代事件事实和看点,不能直接空降观点\n"
            f"- 来源表达用'公开信息显示'、'平台数据显示'、'从目前公开资料看'\n"
            f"- 开头禁止'据X报道'、'X网报道'\n"
            f"- 正文避免'根据X报道'、'消息称'等转载稿口吻\n"
            f"- 不造谣，不扩写未证实隐私\n"
            f"- 不要财经政治理论腔，不要古文典故\n"
            f"- 每段1-3句，口语化，有态度\n"
            f"- 标题12-24字，有看点但不标题党"
        )

        generation_source = "llm"
        try:
            raw = await self.llm.chat_completion(
                self.system_prompt,
                user_prompt,
                temperature=self.temperature,
                max_tokens=3000,
            )
        except Exception as exc:
            logger.error("娱乐 LLM 调用失败，使用模板兜底: topic=%s err=%s", topic, exc)
            generation_source = "fallback_llm_error"
            title, digest, content_md = self._fallback(topic, stance)
        else:
            try:
                title, digest, content_md = self._parse_response(raw, topic)
                logger.info("娱乐文本解析成功: topic=%s raw_len=%d", topic, len(raw))
            except Exception as exc:
                logger.error("娱乐 LLM 解析失败，使用模板兜底: topic=%s err=%s", topic, exc)
                generation_source = "fallback_parse_error"
                title, digest, content_md = self._fallback(topic, stance)

        content_md = finalize_article(content_md, max_chars=self.max_chars)
        content_html = md_lib.markdown(content_md, extensions=["tables"])
        cn_chars = count_cn_chars(content_md)

        if generation_source != "llm":
            logger.warning(
                "娱乐文章使用兜底模板: title=%s source=%s chars=%d topic=%s",
                title, generation_source, cn_chars, topic,
            )
        if cn_chars < self.min_chars:
            logger.warning(
                "娱乐文章字数偏少: %s (%d字 < %d字, source=%s)",
                title, cn_chars, self.min_chars, generation_source,
            )

        logger.info("娱乐文章生成完成: %s (%d字, 最大%d字)", title, cn_chars, self.max_chars)
        return {
            "title": title,
            "digest": digest,
            "content_markdown": content_md,
            "content_html": content_html,
            "style_score": 85,
        }

    @staticmethod
    def _parse_response(raw: str, topic: str) -> tuple[str, str, str]:
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

    @staticmethod
    def _fallback(topic: str, stance: str | None) -> tuple[str, str, str]:
        stance_text = stance or "热闹背后，更该看作品和观众感受"
        title = topic
        digest = f"围绕[{topic}]的娱乐观察。"
        md = (
            f"公开信息显示，{topic}正在引发观众讨论。真正有意思的地方，不只是它上了热搜，而是观众为什么愿意讨论。\n\n"
            f"如果只看表面，这像是一条普通娱乐新闻。但放到作品、人物和舆论现场里看，"
            f"它其实反映的是观众对内容质量、明星表达和平台热度的重新打分。\n\n"
            f"娱乐新闻当然可以轻松看，但不能只剩情绪。哪些是事实，哪些只是传闻，"
            f"哪些是营销推出来的话题，都需要分清楚。\n\n"
            f"我的判断是：{stance_text}。真正能留下来的，永远不是一时的热搜，而是作品和表达能不能经得起观众回看。"
        )
        return title, digest, md
