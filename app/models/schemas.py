from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


ArticleType = Literal["short", "long"]


class TopicCandidate(BaseModel):
    title: str
    source: str
    hot_score: float = Field(default=0, ge=0)
    summary: str = ""
    source_url: HttpUrl | None = None


class ArticlePreviewRequest(BaseModel):
    topic: str
    article_type: ArticleType = "short"
    stance: str | None = None


class ArticlePreviewResponse(BaseModel):
    title: str
    digest: str
    content_markdown: str
    content_html: str
    risk_level: Literal["low", "medium", "high"]
    style_score: int = Field(ge=0, le=100)


class PublishArticleRequest(BaseModel):
    topic: str
    article_type: ArticleType = "short"
    source_url: HttpUrl | None = None
    cover_image_path: str | None = None
    stance: str | None = None


class PublishArticleResponse(BaseModel):
    title: str
    draft_media_id: str
    publish_id: str | None = None
    article_url: str | None = None
    publish_status: str
    fallback_mode: Literal["full_publish", "draft_only"]


class WechatArticlePayload(BaseModel):
    title: str
    author: str
    digest: str
    content: str
    content_source_url: str = ""
    thumb_media_id: str
    need_open_comment: int = 1
    only_fans_can_comment: int = 0


class WechatPublishResult(BaseModel):
    draft_media_id: str
    publish_id: str | None = None
    article_url: str | None = None
    publish_status: str
    fallback_mode: Literal["full_publish", "draft_only"]

