"""娱乐模块配置。"""

from app.modules.base import ScheduleSlot

MODULE_NAME = "entertainment"
DISPLAY_NAME = "娱乐观察"
AUTHOR = "现象观察"

SELECTOR_CONFIG = {
    "priority_keywords": {
        "entertainment": [
            "娱乐", "明星", "演员", "导演", "电影", "电视剧", "剧集", "综艺", "音乐", "歌手",
            "票房", "热播", "定档", "上映", "首映", "院线", "影评", "口碑", "收视", "选秀",
            "演唱会", "粉丝", "艺人", "网红", "直播", "短剧", "综艺节目", "红毯", "时尚",
        ],
        "culture_life": [
            "文化", "生活方式", "旅游", "美食", "消费潮流", "游戏", "体育", "社交平台", "热搜",
        ],
    },
    "downrank_keywords": [
        "财经", "经济", "金融", "股市", "a股", "港股", "美股", "基金", "债券", "汇率",
        "利率", "降息", "加息", "通胀", "cpi", "ppi", "gdp", "房地产", "楼市",
        "外交", "军事", "战争", "军演", "制裁", "关税", "峰会",
    ],
    # 娱乐模块的质量过滤：避开财经/严肃国际政治，不过滤娱乐词本身。
    "blacklist_keywords": [
        "股市", "a股", "港股", "美股", "基金", "债券", "汇率", "降息", "加息", "cpi", "ppi", "gdp",
        "军事", "军演", "武器", "导弹", "战争", "冲突", "制裁", "外交", "峰会",
    ],
}

WRITER_CONFIG = {
    "min_chars": 300,
    "max_chars": 500,
    "temperature": 0.72,
    "frequency_penalty": 0.3,
    "presence_penalty": 0.2,
}

# 先建立娱乐模块但默认不启用；只有 ACTIVE_MODULE=entertainment 或显式 ArticlePipeline("entertainment") 才会用。
# 时间为北京时间(调度器固定 Asia/Shanghai,自动换算机器时区)。
# 三个时段贴合 sharedchat/gpt-5.5 公益站额度重置窗口(北京 12/15/18 点重置后约1小时充足),
# 错后 5 分钟避开整点抢额度高峰;各时段独立 batch_type,避免 job_id 冲突。
SCHEDULE_SLOTS = [
    ScheduleSlot(hour=12, minute=5, batch_type="noon", count=1),
    ScheduleSlot(hour=15, minute=5, batch_type="afternoon", count=1),
    ScheduleSlot(hour=18, minute=5, batch_type="evening", count=1),
]
