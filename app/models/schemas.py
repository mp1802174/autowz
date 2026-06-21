from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class TopicCandidate(BaseModel):
    title: str
    source: str
    hot_score: float = Field(default=0, ge=0)
    summary: str = ""
    source_url: Optional[HttpUrl] = None


class ArticlePreviewRequest(BaseModel):
    topic: str
    stance: Optional[str] = None


class ArticlePreviewResponse(BaseModel):
    title: str
    digest: str
    content_markdown: str
    content_html: str
    risk_level: Literal["low", "medium", "high"]
    style_score: int = Field(ge=0, le=100)


class PublishArticleRequest(BaseModel):
    topic: str
    source_url: Optional[HttpUrl] = None
    cover_image_path: Optional[str] = None
    stance: Optional[str] = None


class PublishArticleResponse(BaseModel):
    title: str
    draft_media_id: str
    publish_id: Optional[str] = None
    article_url: Optional[str] = None
    publish_status: str
    fallback_mode: Literal["full_publish", "draft_only"] = "draft_only"


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
    publish_id: Optional[str] = None
    article_url: Optional[str] = None
    publish_status: str
    fallback_mode: Literal["full_publish", "draft_only"]
    cover_media_id: str = ""
    error_code: Optional[int] = None
    error_message: Optional[str] = None
