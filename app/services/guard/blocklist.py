"""集中管理风险词库。

设计原则：
- HIGH_RISK_TERMS：命中即拦截。这些题材在公众号侧极易触发限流、删文、降权
  甚至封号。无论上下文如何，一律不生成、不发布。
- MEDIUM_RISK_TERMS：命中标记为 medium。允许通过但需要人工二审，例如中美博
  弈、国际地缘冲突，写法上要克制。
- DOWNRANK_TERMS：仅用于选题降权（不拦截），通常是大规模劳资/失业等敏感民
  生话题。
"""

# === 高风险：直接拦截 ===
HIGH_RISK_TERMS: tuple[str, ...] = (
    # 涉政体 / 国安
    "颠覆", "推翻政权", "反动", "分裂", "政变", "暴动", "国家机密",
    "国安委", "纪委", "中纪委", "维稳", "黑监狱", "信访",
    # 涉港澳台
    "台独", "港独", "藏独", "疆独", "台海", "武统", "和统",
    "台湾", "国台办", "对台",
    "蔡英文", "赖清德", "民进党",
    "占中", "黄之锋", "黎智英",
    "一国两制", "九二共识",
    # 涉军 / 武力
    "军演", "实弹", "导弹试射", "东风导弹", "解放军", "战机绕台",
    "航母编队", "战备", "动武",
    # 涉民族 / 宗教
    "新疆", "西藏", "维吾尔", "达赖", "法轮", "清真寺",
    # 涉群体性事件
    "群体性事件", "维权", "上访", "示威", "游行", "抗议", "骚乱",
    "罢工", "罢课", "罢市", "占领", "聚集",
    # 涉领导人 / 高层（评论性表达）
    "习近平", "习主席", "李强", "蔡奇", "丁薛祥",
    "政治局常委", "中央军委",
    # 涉煽动 / 谣言
    "造谣", "未经证实", "内幕消息", "小道消息", "泄密",
    "封杀", "全民声讨", "人肉搜索", "网暴",
    "死刑", "处决", "血债",
)

# === 中风险：允许，但标记 medium，写作时回避煽动性表达 ===
MEDIUM_RISK_TERMS: tuple[str, ...] = (
    # 涉中美博弈（"中美"为高频敏感词，公众号侧极易限流，统一标 medium）
    "中美", "中欧", "中日", "中韩",
    "对华遏制", "对华制裁", "中国威胁论",
    "贸易战", "关税战", "脱钩", "卡脖子", "芯片战", "科技战",
    # 涉国际冲突 / 敏感地区
    "俄乌", "乌克兰战争", "普京", "泽连斯基",
    "以色列", "哈马斯", "巴以", "加沙",
    "伊朗", "美伊", "伊核", "霍尔木兹", "革命卫队",
    "朝鲜", "朝俄", "金正恩",
    "古巴", "委内瑞拉", "叙利亚",
    "南海", "印太",
    # 涉外交制裁 / 国际博弈表达
    "制裁", "禁运", "断供",
    # 涉特朗普 / 拜登（评论性语境）
    "特朗普", "拜登", "白宫",
    # 涉极端劳资 / 失业潮
    "大规模裁员", "裁员潮", "失业潮", "下岗潮",
    "996", "007",
)

# === 降权：选题阶段扣分但不拦截 ===
DOWNRANK_TERMS: tuple[str, ...] = (
    "明星", "恋情", "离婚", "绯闻", "八卦", "塌房", "网红",
    "穿搭", "颜值", "综艺", "粉丝", "猎奇", "奇葩", "震惊",
    "吃瓜",
)


def _normalize(text: str) -> str:
    return (text or "").lower()


def match_high_risk(text: str) -> str | None:
    """返回命中的第一个高风险词，未命中返回 None。"""
    t = _normalize(text)
    for term in HIGH_RISK_TERMS:
        if term.lower() in t:
            return term
    return None


def match_medium_risk(text: str) -> str | None:
    """返回命中的第一个中风险词，未命中返回 None。"""
    t = _normalize(text)
    for term in MEDIUM_RISK_TERMS:
        if term.lower() in t:
            return term
    return None


def is_topic_blocked(text: str) -> tuple[bool, str | None]:
    """选题级硬拦截：仅看高风险。返回 (是否拦截, 命中词)。"""
    hit = match_high_risk(text)
    return (hit is not None), hit


def is_topic_risky(text: str) -> tuple[bool, str, str | None]:
    """选题级风险检查：高/中风险均拦截。返回 (是否拦截, 等级, 命中词)。

    用于自动批次的 selector：自动管线一律不碰 high/medium，避免限流。
    手动 publish 路径仍用 is_topic_blocked，只拦 high，medium 由用户自决。
    """
    hit_high = match_high_risk(text)
    if hit_high:
        return True, "high", hit_high
    hit_med = match_medium_risk(text)
    if hit_med:
        return True, "medium", hit_med
    return False, "low", None
