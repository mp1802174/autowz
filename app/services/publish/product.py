"""发布层标准数据结构(与渠道无关)。

生成层只产出 ArticleProduct,不关心"发到哪";发布层(Channel/Router)消费它。
这是"生成与发布解耦"的契约层。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ArticleProduct:
    """一篇文章的标准产物,与具体渠道解耦。"""

    title: str
    digest: str
    content_html: str
    content_md: str = ""
    author: str = ""
    cover_path: str | None = None
    tags: list[str] = field(default_factory=list)
    source_url: str = ""
    # 是否注入"AI 辅助生成"声明(合规,见 GUIDE §8.5;走质量+合规路线,不做规避)
    ai_disclosure: bool = True
    # 质量门评分(0-100);Router 据此拒发低质内容,落实项目第一纲领
    quality_score: float | None = None
    # 关联数据库文章 id(可选)
    article_id: int | None = None


@dataclass
class PublishResult:
    """单个渠道的发布结果(统一结构)。"""

    channel: str
    ok: bool
    status: str  # 渠道返回的状态字符串
    url: str | None = None
    draft_id: str | None = None
    skipped_reason: str | None = None  # 非空表示被跳过(质量门 / 未就绪)
    error: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class ChannelStats:
    """渠道侧数据回收结构(P2 数据闭环用)。"""

    channel: str
    read_count: int | None = None
    like_count: int | None = None
    share_count: int | None = None
    raw: dict = field(default_factory=dict)
