"""规则版内容质量校验器。

# ⚠️ 项目第一纲领(不可违背):质量第一,质量低不如不做。

定位:零成本、确定性的「第一道质量闸」。专门拦截大模型最典型的低质产物 ——
退化长句(停不下来的无标点超长句)、断头结尾(被硬截断)、字符/片段重复、
段落畸形、字数不足。命中即判不合格,交由上层弃稿或重生成。

它不替代语义层评审(信息增量、像不像机器),那是 P2 的 LLM 评审职责;
本模块只做"机器一眼可判"的硬伤拦截,快而稳。
"""

import re
from dataclasses import dataclass, field
from typing import List

# 句末标点(中英文):用于切句、判断结尾是否自然收束。
SENTENCE_ENDINGS = "。！？!?…"
# 结尾允许的收束字符(含引号/省略号/右括号等)。
CLOSING_CHARS = SENTENCE_ENDINGS + "”』」)）\""

# 阈值(可按模块需要调整;默认偏宽松,只拦明显硬伤)。
MAX_SENTENCE_CHARS = 80      # 单句中文字数上限,超过视为退化长句
MAX_PARAGRAPH_CHARS = 320    # 单段中文字数上限,超过视为畸形段落
MIN_PARAGRAPHS = 2           # 正文至少分段数
NGRAM_N = 6                  # 重复检测的片段长度
NGRAM_MAX_REPEAT = 3         # 同一片段最多出现次数


class ContentQualityError(Exception):
    """内容未通过质量校验。携带具体不合格原因,供上层日志与决策。"""

    def __init__(self, reasons: List[str]) -> None:
        self.reasons = reasons
        super().__init__("内容质量不合格: " + "; ".join(reasons))


@dataclass
class QualityResult:
    """质量校验结果。

    - passed: 是否通过
    - score: 0-100 质量分(用于替代硬编码 style_score)
    - reasons: 不合格原因列表(passed=True 时为空)
    """

    passed: bool
    score: int
    reasons: List[str] = field(default_factory=list)


def count_cn_chars(text: str) -> int:
    return sum(1 for c in text if "一" <= c <= "鿿")


def _split_sentences(text: str) -> List[str]:
    """按句末标点切句,保留标点。换行也作为软边界。"""
    # 先把换行视为句子边界,避免"列表项无句号"被误判为超长句。
    parts = re.split(r"(?<=[" + re.escape(SENTENCE_ENDINGS) + r"])|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


def _max_ngram_repeat(text: str, n: int) -> int:
    """返回出现次数最多的 n-gram(仅中文)的重复次数。"""
    cn = [c for c in text if "一" <= c <= "鿿"]
    if len(cn) < n:
        return 0
    counts: dict[str, int] = {}
    best = 0
    for i in range(len(cn) - n + 1):
        gram = "".join(cn[i:i + n])
        counts[gram] = counts.get(gram, 0) + 1
        if counts[gram] > best:
            best = counts[gram]
    return best


def check_quality(
    title: str,
    content_md: str,
    *,
    min_chars: int = 200,
    max_chars: int = 700,
    max_sentence_chars: int = MAX_SENTENCE_CHARS,
    max_paragraph_chars: int = MAX_PARAGRAPH_CHARS,
) -> QualityResult:
    """对单篇文章做规则质量校验。

    返回 QualityResult;不抛异常(是否抛由调用方决定)。
    评分从 100 起扣:每类硬伤按严重度扣分,低于 80 视为不合格。
    """
    reasons: List[str] = []
    score = 100

    body = (content_md or "").strip()
    cn = count_cn_chars(body)

    # 1) 字数不足/超限
    if cn < min_chars:
        shortage = min_chars - cn
        if shortage <= min_chars * 0.10:
            # 差不到10%:轻微扣分但不硬否决(差几个字不等于低质)
            reasons.append(f"字数略少: {cn} < {min_chars} (差{shortage}字)")
            score -= 10
        else:
            # 差超过10%:严重不足,扣分且硬否决
            reasons.append(f"字数严重不足: {cn} < {min_chars} (差{shortage}字)")
            score -= 25
    elif cn > max_chars:
        reasons.append(f"字数超限: {cn} > {max_chars}")
        score -= 15

    # 2) 结尾被硬切 / 断头(末字符不是自然收束符号)
    if body:
        last = body.rstrip()[-1:]
        if last and last not in CLOSING_CHARS:
            reasons.append(f"结尾未自然收束(疑似截断),末字符={last!r}")
            score -= 30

    # 3) 退化长句:任一句中文字数超限
    long_sentences = [s for s in _split_sentences(body)
                      if count_cn_chars(s) > max_sentence_chars]
    if long_sentences:
        worst = max(count_cn_chars(s) for s in long_sentences)
        reasons.append(
            f"存在退化超长句: {len(long_sentences)}处,最长{worst}字 "
            f"(阈值{max_sentence_chars})"
        )
        score -= 35

    # 4) 畸形段落:单段过长
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    long_paras = [p for p in paragraphs if count_cn_chars(p) > max_paragraph_chars]
    if long_paras:
        worst = max(count_cn_chars(p) for p in long_paras)
        reasons.append(f"存在超长段落: 最长{worst}字 (阈值{max_paragraph_chars})")
        score -= 20

    # 5) 分段过少(整篇糊成一坨)
    if cn >= min_chars and len(paragraphs) < MIN_PARAGRAPHS:
        reasons.append(f"分段过少: {len(paragraphs)}段")
        score -= 15

    # 6) 片段重复(退化的另一种表现)
    repeat = _max_ngram_repeat(body, NGRAM_N)
    if repeat > NGRAM_MAX_REPEAT:
        reasons.append(f"片段重复: 某{NGRAM_N}字片段重复{repeat}次")
        score -= 25

    # 7) 标题异常(空/过长/含 markdown 残留)
    t = (title or "").strip()
    if not t:
        reasons.append("标题为空")
        score -= 20
    elif len(t) > 40:
        reasons.append(f"标题过长: {len(t)}字")
        score -= 10

    score = max(0, min(100, score))
    passed = score >= 80 and not any(
        r.startswith(("结尾未自然收束", "存在退化超长句", "字数严重不足", "字数超限"))
        for r in reasons
    )
    return QualityResult(passed=passed, score=score, reasons=reasons)
