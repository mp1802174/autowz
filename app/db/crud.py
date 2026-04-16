from datetime import date

from sqlalchemy.orm import Session

from app.db.models import Article, Topic, WechatPublishRecord


# ---- Topic ----

def save_topic(session: Session, **kwargs) -> Topic:
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
