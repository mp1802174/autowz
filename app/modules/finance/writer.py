"""财经模块 Writer - 数据驱动解读型写作

重构后的 writer,专注于财经数据解读,去除 AI 味和机器指纹。
"""

# ⚠️ 项目第一纲领(不可违背 —— 换任何开发者/维护者/AI 都须第一时间遵循):
#    质量第一,质量低不如不做。本项目的生存前提,是产出"有真实信息增量、
#    读起来不像机器"的高质量内容;宁可少发、不发,也不发低质内容。
#    走质量路线,不走规避路线 —— 目标是"标了 AI 也不掉流量、被检测也不算
#    低质",而非赌平台检测不到。任何为数量/效率/规避而牺牲质量的改动,
#    都违背项目根本目标。详见 README 顶部纲领 与 GUIDE.md §8.3。

import logging
from typing import Optional, Tuple

import markdown as md_lib

from app.services.content_length import (
    MAX_ARTICLE_CHARS,
    MIN_ARTICLE_CHARS,
    count_cn_chars,
    finalize_article,
)
from app.services.llm.client import LLMClient, get_llm_client
from app.services.prompts import BASE_SYSTEM_PROMPT
from app.services.quality import check_quality

logger = logging.getLogger("autowz.finance.writer")


def _quality_char_bounds(min_chars: int, max_chars: int) -> tuple[int, int]:
    """质量闸字数范围放宽：目标字数由 prompt/finalize 控制。"""
    return max(1, min_chars - 100), max_chars + 200

# 财经模块专属规则(项目级约束由 BASE_SYSTEM_PROMPT 提供,不在此重复)
FINANCE_PROMPT = """
## 模块定位 — 数据驱动财经解读
不做新闻搬运工，做数据翻译官。用数据说话，把冰冷数字转化为对读者钱包和生计有意义的洞察。

## 模块写作结构(严格遵守)

### 1. 事实开头(40-70 字,1 段)
- 第一段必须有事实依据和新闻事实，让读者知道文章依据哪件事/哪组数据；但开头方式不拘一格，不要每篇都同一句式。
- 来源交代可以多样化(如"数据显示""公司公告""交易所披露信息""从已披露信息看")，也可以隐含在叙述中，不要每段前面加固定前缀。
- 第二句快速点出"这和读者的关系"(存款/理财/购车成本/投资机会/就业形势)
- 示例:"近期多家银行下调存款利率，对普通家庭来说，这不只是银行的一次调整，而是现金、理财和房贷都要重新算账的信号。"

### 2. 核心数据(70-110 字,1-2 段)
- 核心数据 + 同比/环比/历史对比
- 用简洁的列表或小表格呈现关键数字
- 每个数据必带来源("中汽协数据""国家统计局公布")
- 禁止:大段引用、专家原话堆砌、流水账式罗列

### 3. 解读分析(90-140 字,1-2 段)
- 数据背后的驱动因素(政策/成本/技术/消费习惯)
- 横向对比(与其他行业/国家/历史时期)
- 拆解主要矛盾(供给 vs 需求,短期 vs 长期)

### 4. 影响推演(60-100 字,1 段)
- 对产业链(上下游)的影响
- 对消费者(钱包/选择/体验)的影响
- 对投资(相关板块/风险)的影响

### 5. 明确判断(40-80 字,1 段)
- 给出清晰结论，不模棱两可
- 可以是"继续看多""谨慎观望""拐点已现"
- 结尾留一个思考点或反问

## 模块语言要求
- 具体数字 + 单位(不说"很多"，说"155.4 万辆")
- 口语化转折("说句不中听的""实际情况是")
- 判断鲜明，不骑墙
"""


class DataDrivenWriter:
    """数据驱动解读型写作器"""

    def __init__(
        self,
        author: str,
        llm_client: Optional[LLMClient] = None,
        *,
        min_chars: int = MIN_ARTICLE_CHARS,
        max_chars: int = MAX_ARTICLE_CHARS,
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
        # 项目基础约束 + 财经模块差异
        self.system_prompt = BASE_SYSTEM_PROMPT.format(
            min_chars=min_chars,
            max_chars=max_chars,
        ) + FINANCE_PROMPT

    async def generate(
        self,
        topic: str,
        stance: Optional[str] = None,
        context_text: str = "",
    ) -> dict:
        """生成数据解读型文章

        Args:
            topic: 话题标题
            stance: 立场倾向(可选)
            context_text: 素材文本(搜狗搜索结果)

        Returns:
            包含 title/digest/content_markdown/content_html/style_score 的 dict
        """
        stance_hint = f"\n立场倾向:{stance}" if stance else ""
        context_block = f"\n\n素材:\n{context_text}" if context_text else ""

        user_prompt = (
            f"话题:{topic}{stance_hint}{context_block}\n\n"
            f"请写一篇数据驱动的财经解读文章,结构严格遵守:\n"
            f"1. 事实开头(40-70字):用自然方式交代新闻事实(不要每篇套同一句式),迅速点出与读者钱包的关系\n"
            f"2. 核心数据(70-110字):只写最关键数字+对比,必带来源\n"
            f"3. 解读分析(90-140字):抓一个主要驱动因素和一个核心矛盾,不要铺开写\n"
            f"4. 影响推演(60-100字):点到产业链/消费者/投资中最相关的一项\n"
            f"5. 明确判断(40-80字):清晰结论,不骑墙\n\n"
            f"硬性要求:\n"
            f"- 全文{self.min_chars}-{self.max_chars}字\n"
            f"- 第一段必须有事实依据和新闻事实,不能直接空降观点;但开头方式不拘一格\n"
            f"- 所有数字必须来自素材,禁止编造;素材里没有的数字(销量/百分比/金额/排名/同比环比)一律不写,宁可用'多数''明显''大幅'等模糊表述\n"
            f"- 每个数据必带来源\n"
            f"- 严禁'据X报道'、'根据X报道'、'X网报道'、'消息称'等转载稿口吻\n"
            f"- 来源自然隐含交代,不要在每段前面加'公开信息显示'等固定前缀\n"
            f"- 禁止'从市场逻辑看'套话\n"
            f"- 禁止AI套话和整齐排比\n"
            f"- 每段1-3句,偶尔1句独立成段\n"
            f"- 单句不超过80个中文汉字;长句必须拆短,不要无标点长段\n"
            f"- 最后一段必须完整收束,不能半句截断\n"
            f"- 标题12-20字,句式不要每篇雷同(数字/反差/疑问/直陈轮换挑最贴切的一种),不标题党"
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
        logger.info("LLM文本解析成功: topic=%s raw_len=%d", topic, len(raw))

        # Phase 1: finalize_article 已改为只裁剪,不加"(全文共X字)"
        content_md = finalize_article(content_md, max_chars=self.max_chars)
        # 启用 Markdown 表格扩展
        content_html = md_lib.markdown(content_md, extensions=['tables'])
        cn_chars = count_cn_chars(content_md)

        if cn_chars < self.min_chars:
            logger.warning(
                "文章生成字数偏少: %s (%d字 < %d字)",
                title, cn_chars, self.min_chars,
            )

        logger.info(
            "文章生成完成: %s (%d字, 最大%d字)",
            title, cn_chars, self.max_chars,
        )

        quality_min, quality_max = _quality_char_bounds(self.min_chars, self.max_chars)
        quality = check_quality(
            title,
            content_md,
            min_chars=quality_min,
            max_chars=quality_max,
        )
        if not quality.passed:
            logger.warning(
                "文章规则质量分偏低: %s score=%s reasons=%s",
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
        """解析LLM输出,提取标题、摘要、正文"""
        lines = raw.strip().split("\n")

        title = ""
        digest = ""
        body_start = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # 第一个非空行是标题
            if not title:
                title = stripped.lstrip("#").strip()
                continue

            # 第二个非空行是摘要(可能带 > 引用标记)
            if not digest:
                digest = stripped.lstrip(">").strip()
                # 去掉"摘要:"等前缀
                for prefix in ("摘要:", "摘要：", "摘要 ", "摘要", "概要:", "概要：", "概要"):
                    if digest.startswith(prefix):
                        digest = digest[len(prefix):].strip()
                        break
                body_start = i + 1
                break

        content_md = "\n".join(lines[body_start:]).strip()

        # 兜底
        if not title:
            title = topic
        if not digest:
            digest = f"围绕[{topic}]的数据解读文章。"
        if not content_md:
            content_md = raw.strip()

        # 微信标题限制64字符
        if len(title) > 64:
            title = title[:62] + "…"

        # 微信摘要限制120字符
        if len(digest) > 120:
            digest = digest[:118] + "…"

        return title, digest, content_md
