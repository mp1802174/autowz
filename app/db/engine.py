from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.mysql_dsn,
            pool_size=settings.mysql_pool_size,
            pool_recycle=settings.mysql_pool_recycle,
            echo=settings.app_debug,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def get_db_session():
    """获取数据库 session 的上下文管理器。"""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """创建所有表。"""
    from app.db.models import Base  # noqa: F811
    Base.metadata.create_all(get_engine())
