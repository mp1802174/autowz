from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db.models import Article, Topic, WechatPublishRecord


# ---- Topic ----

def save_topic(session: Session, **kwargs) -> Topic:
    """纯 INSERT，不做去重。推荐在需要去重的场景使用 save_topic_upsert。"""
    topic = Topic(**kwargs)
    session.add(topic)
    session.flush()
    return topic


def save_topic_upsert(session: Session, **kwargs) -> Topic:
    """按 (title + batch_date) 去重的保存：已存在则返回已有记录，否则新建。"""
    title = kwargs.get("title")
    batch_date_val = kwargs.get("batch_date")
    if title and batch_date_val:
        existing = (
            session.query(Topic)
            .filter(Topic.title == title, Topic.batch_date == batch_date_val)
            .first()
        )
        if existing:
            return existing
    topic = Topic(**kwargs)
    session.add(topic)
    session.flush()
    return topic


def get_topics_by_date(session: Session, batch_date: date | None = None) -> list[Topic]:
    d = batch_date or date.today()
    return session.query(Topic).filter(Topic.batch_date == d).order_by(Topic.hot_score.desc()).all()


def get_selected_topics(session: Session, batch_date: date | None = None) -> list[Topic]:
    d = batch_date or date.today()
    return (
        session.query(Topic)
        .filter(Topic.batch_date == d, Topic.status == "selected")
        .order_by(Topic.hot_score.desc())
        .all()
    )


def get_recent_selected_topics(session: Session, days: int = 3) -> list[Topic]:
    """获取近 N 天已选话题（跨天去重）。"""
    since = date.today() - timedelta(days=days)
    return (
        session.query(Topic)
        .filter(Topic.batch_date >= since, Topic.status == "selected")
        .order_by(Topic.batch_date.desc(), Topic.hot_score.desc())
        .all()
    )


def update_topic_status(session: Session, topic_id: int, status: str) -> None:
    session.query(Topic).filter(Topic.id == topic_id).update({"status": status})


# ---- Article ----

def save_article(session: Session, **kwargs) -> Article:
    article = Article(**kwargs)
    session.add(article)
    session.flush()
    return article


def get_article_by_id(session: Session, article_id: int) -> Article | None:
    return session.query(Article).filter(Article.id == article_id).first()


def update_article_status(session: Session, article_id: int, status: str, **extra) -> None:
    updates = {"status": status, **extra}
    session.query(Article).filter(Article.id == article_id).update(updates)


def get_articles_by_status(session: Session, status: str) -> list[Article]:
    return session.query(Article).filter(Article.status == status).all()


# ---- WechatPublishRecord ----

def save_publish_record(session: Session, **kwargs) -> WechatPublishRecord:
    record = WechatPublishRecord(**kwargs)
    session.add(record)
    session.flush()
    return record


def update_publish_record(session: Session, record_id: int, **updates) -> None:
    session.query(WechatPublishRecord).filter(WechatPublishRecord.id == record_id).update(updates)


def get_pending_publish_records(session: Session) -> list[WechatPublishRecord]:
    return (
        session.query(WechatPublishRecord)
        .filter(WechatPublishRecord.publish_status.in_(["pending", "submitted"]))
        .all()
    )


def get_random_published_articles(
    session: Session, count: int = 3, exclude_article_id: int | None = None
) -> list[dict]:
    """随机获取已发表文章用于导读区块，返回 title/article_url/content_html 字段。"""
    from sqlalchemy import func as sa_func
    query = (
        session.query(Article.id, Article.title, Article.content_html, WechatPublishRecord.article_url)
        .join(WechatPublishRecord, WechatPublishRecord.article_id == Article.id)
        .filter(
            WechatPublishRecord.publish_status == "success",
            WechatPublishRecord.article_url != "",
            WechatPublishRecord.article_url.isnot(None),
        )
    )
    if exclude_article_id is not None:
        query = query.filter(Article.id != exclude_article_id)
    rows = query.order_by(sa_func.random()).limit(count).all()
    return [
        {"id": r.id, "title": r.title, "content_html": r.content_html, "article_url": r.article_url}
        for r in rows
    ]
