from datetime import date

from sqlalchemy import (
    BigInteger, Column, Date, DateTime, ForeignKey, Index,
    Numeric, String, Text, func,
)
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Topic(Base):
    __tablename__ = "topics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    source = Column(String(50), nullable=False, comment="来源: weibo/baidu")
    hot_score = Column(Numeric(10, 2), default=0)
    conflict_score = Column(Numeric(10, 2), default=0)
    summary = Column(Text, default="")
    source_url = Column(Text, default="")
    collected_at = Column(DateTime, default=func.now())
    batch_date = Column(Date, default=date.today, index=True)
    status = Column(String(30), default="collected", comment="collected/selected/used")

    articles = relationship("Article", back_populates="topic")

    __table_args__ = (
        Index("ix_topics_batch_status", "batch_date", "status"),
    )


class Article(Base):
    __tablename__ = "articles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    topic_id = Column(BigInteger, ForeignKey("topics.id"), nullable=True)
    article_type = Column(String(10), nullable=False, comment="short/long")
    title = Column(String(500), default="")
    digest = Column(Text, default="")
    content_md = Column(LONGTEXT, default="")
    content_html = Column(LONGTEXT, default="")
    style_score = Column(Numeric(5, 2), default=0)
    risk_level = Column(String(10), default="low")
    status = Column(
        String(30), default="drafted",
        comment="drafted/humanized/reviewed/publishing/published/failed",
    )
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    topic = relationship("Topic", back_populates="articles")
    publish_records = relationship("WechatPublishRecord", back_populates="article")

    __table_args__ = (
        Index("ix_articles_status", "status"),
    )


class WechatPublishRecord(Base):
    __tablename__ = "wechat_publish_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    article_id = Column(BigInteger, ForeignKey("articles.id"), nullable=False)
    draft_media_id = Column(String(200), default="")
    publish_id = Column(String(200), default="")
    article_url = Column(Text, default="")
    publish_status = Column(String(30), default="pending")
    raw_response = Column(JSON, nullable=True)
    cover_media_id = Column(String(200), default="")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    article = relationship("Article", back_populates="publish_records")
