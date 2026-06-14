"""财经模块配置

数据驱动型财经内容模块的所有配置参数。
"""

# 模块基础信息
MODULE_NAME = "finance"
DISPLAY_NAME = "财经观察"
AUTHOR = "现象观察"

# 选题配置
SELECTOR_CONFIG = {
    "priority_keywords": {
        "finance": [
            "财经", "经济", "金融", "股市", "a股", "港股", "美股", "基金", "债券", "汇率", "人民币", "美元",
            "利率", "降息", "加息", "通胀", "cpi", "ppi", "gdp", "就业", "消费", "楼市", "房价", "房地产",
            "车企", "产业", "出口", "外贸", "关税", "贸易", "供应链", "平台经济", "民营经济", "财政", "税收",
        ],
        "leaders": [
            "总统", "总理", "主席", "首相", "国王", "王储", "元首", "领导人", "会晤", "峰会", "访华", "访美",
        ],
    },
    "downrank_keywords": [
        "明星", "恋情", "离婚", "绯闻", "八卦", "塌房", "网红", "热舞", "穿搭", "颜值", "综艺", "演唱会", "粉丝",
    ],
    "blacklist_keywords": [
        "娱乐", "明星", "八卦", "绯闻", "恋情", "离婚", "网红", "综艺",
        "体育", "足球", "篮球", "nba", "比赛", "球员",
        "游戏", "电竞", "主播",
    ],
}

# 写作配置
WRITER_CONFIG = {
    "min_chars": 650,
    "max_chars": 750,
    "style": "data_driven_analysis",
    "structure": "hook-data-analysis-impact-conclusion",
}

# 调度配置
SCHEDULE_CONFIG = {
    "enabled": True,
    "cron_hour": 7,      # 每天 7:30
    "cron_minute": 30,
    "daily_count": 1,    # 每天 1 篇
}

# 数据源配置(暂未实现,Phase 2)
DATA_SOURCES = [
    "akshare",   # AKShare 宏观/行业数据
    "tushare",   # Tushare 市场数据
]
