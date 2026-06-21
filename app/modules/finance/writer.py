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
from typing import Optional

import markdown as md_lib

from app.services.content_length import (
    MAX_ARTICLE_CHARS,
    MIN_ARTICLE_CHARS,
    count_cn_chars,
    finalize_article,
)
from app.services.llm.client import LLMClient, get_llm_client

logger = logging.getLogger("autowz.finance.writer")

# 数据驱动解读型 prompt
SYSTEM_PROMPT_TEMPLATE = """你是"现象观察"财经观察机构的数据分析师,为微信公众号撰写财经数据解读文章。

## 核心定位
不做新闻搬运工,做数据翻译官。用数据说话,把冰冷的数字转化为对读者钱包和生计有意义的洞察。

## 写作结构(严格遵守)

### 1. 事实开头(60-100 字,1-2 段)
- 第一段必须先交代"事实式来源 + 新闻事实 + 和读者的关系"
- 可用表达:"公开信息显示""市场数据显示""公司公告显示""交易所披露信息显示""从已披露信息看"
- 第一段不要只抛观点,必须让读者知道文章依据哪件事/哪组数据
- 第二句快速点出"这和读者的关系"(存款/理财/购车成本/投资机会/就业形势)
- **禁止**:"据XX报道""根据XX报道""XX网报道""消息称"开头、背景铺垫、概念解释
- 示例:"公开信息显示,近期多家银行下调存款利率。对普通家庭来说,这不只是银行的一次调整,而是现金、理财和房贷都要重新算账的信号。"

### 2. 数据呈现(200-250 字,2-3 段)
- 核心数据 + 同比/环比/历史对比
- 用简洁的列表或小表格呈现关键数字
- 每个数据**必带来源**("中汽协数据""国家统计局公布")
- **禁止**:大段引用、专家原话堆砌、流水账式罗列

### 3. 解读分析(200-250 字,2-3 段)
- 数据背后的驱动因素(政策/成本/技术/消费习惯)
- 横向对比(与其他行业/国家/历史时期)
- 拆解主要矛盾(供给vs需求,短期vs长期)
- **禁止**:"从市场逻辑看""抓住主要矛盾"等套话

### 4. 影响推演(100-150 字,1-2 段)
- 对产业链(上下游)的影响
- 对消费者(钱包/选择/体验)的影响
- 对投资(相关板块/风险)的影响

### 5. 明确判断(50-80 字,1 段)
- 给出清晰结论,不模棱两可
- 可以是"继续看多""谨慎观望""拐点已现"
- 结尾留一个思考点或反问
- **禁止**:关注/点赞/转发引导、空洞总结

## 语言风格

### 必须做到:
- 句子长短交错,每段1-3句
- 偶尔1句独立成段制造节奏
- 具体数字+单位(不说"很多",说"155.4万辆")
- 口语化转折("说句不中听的""实际情况是")
- 判断鲜明,不骑墙

### 严格禁止:
- 转载稿口吻:"据XX报道""根据XX报道""XX网报道""消息称"。需要交代来源时,改写成"公开信息显示""数据显示""材料显示"。
- 不能完全省略新闻事实和信息来源,否则文章会显得突兀。
- AI套话:"在这个XX的时代""不得不说""众所周知""耐人寻味""这值得深思""这背后折射出"
- 机械序列词:"首先/其次/最后""综上所述""总而言之"
- 整齐排比和工整对仗
- 公知体(看似中立实则站西方立场)
- 空洞抒情和骑墙式总结
- 超过3句的段落(必须拆开)

## 字数控制
- 全文严格{min_chars}-{max_chars}字(中文汉字,标点不计)
- 宁可少写几句精炼有力,也不凑字数注水

## 输出格式
只输出:
1. 第一行:标题(12-20字,带具体数字或反差,不夸张不标题党)
2. 空行
3. 摘要(一句话,20字以内,有态度有信息量)
4. 空行
5. 正文(Markdown格式)

**不要**输出任何说明、思考过程、字数统计。
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
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            min_chars=min_chars,
            max_chars=max_chars,
        )

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
            f"1. 事实开头(60-100字):用'公开信息显示/市场数据显示/公司公告显示/从已披露信息看'交代新闻事实,再点出与读者钱包的关系\n"
            f"2. 数据呈现(200-250字):核心数字+对比,必带来源\n"
            f"3. 解读分析(200-250字):驱动因素+横向对比+拆解矛盾\n"
            f"4. 影响推演(100-150字):产业链/消费者/投资影响\n"
            f"5. 明确判断(50-80字):清晰结论,不骑墙\n\n"
            f"硬性要求:\n"
            f"- 全文{self.min_chars}-{self.max_chars}字\n"
            f"- 第一段必须有事实式来源和新闻事实,不能直接空降观点\n"
            f"- 所有数字必须来自素材,禁止编造;素材里没有的数字(销量/百分比/金额/排名/同比环比)一律不写,宁可用'多数''明显''大幅'等模糊表述\n"
            f"- 每个数据必带来源\n"
            f"- 禁止'据X报道'、'根据X报道'、'X网报道'、'消息称'等转载稿口吻\n"
            f"- 需要交代来源时,用'公开信息显示'、'数据显示'、'材料显示'\n"
            f"- 禁止'从市场逻辑看'套话\n"
            f"- 禁止AI套话和整齐排比\n"
            f"- 每段1-3句,偶尔1句独立成段\n"
            f"- 标题12-20字,句式不要每篇雷同(数字/反差/疑问/直陈轮换挑最贴切的一种),不标题党"
        )

        raw = await self.llm.chat_completion(
            self.system_prompt,
            user_prompt,
            temperature=self.temperature,
            max_tokens=3000,
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

        # Phase 1: 单次生成,style_score 提升到 85(因为去除了双LLM的AI指纹)
        return {
            "title": title,
            "digest": digest,
            "content_markdown": content_md,
            "content_html": content_html,
            "style_score": 85,
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

