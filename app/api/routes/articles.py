from datetime import date

from fastapi import APIRouter, HTTPException

from app.db.crud import get_article_by_id, get_topics_by_date
from app.db.engine import get_db_session
from app.models.schemas import (
    ArticlePreviewRequest,
    ArticlePreviewResponse,
    PublishArticleRequest,
    PublishArticleResponse,
)
from app.services.pipeline import ArticlePipeline


router = APIRouter(prefix="/articles", tags=["articles"])
pipeline = ArticlePipeline()


@router.post("/preview", response_model=ArticlePreviewResponse)
async def preview_article(payload: ArticlePreviewRequest) -> ArticlePreviewResponse:
    return await pipeline.generate_preview(payload)


@router.post("/publish", response_model=PublishArticleResponse)
async def publish_article(payload: PublishArticleRequest) -> PublishArticleResponse:
    try:
        return await pipeline.publish(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/collect")
async def collect_topics():
    """手动触发热点采集。"""
    saved = await pipeline.collect_topics()
    return {"count": len(saved), "topics": saved}


@router.get("/topics")
async def list_today_topics():
    """获取今日采集的话题列表。"""
    with get_db_session() as session:
        topics = get_topics_by_date(session, date.today())
        return [
            {
                "id": t.id,
                "title": t.title,
                "source": t.source,
                "hot_score": float(t.hot_score or 0),
                "summary": t.summary,
                "status": t.status,
            }
            for t in topics
        ]


@router.get("/{article_id}")
async def get_article(article_id: int):
    """获取文章详情。"""
    with get_db_session() as session:
        article = get_article_by_id(session, article_id)
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
        return {
            "id": article.id,
            "title": article.title,
            "article_type": article.article_type,
            "digest": article.digest,
            "content_html": article.content_html,
            "style_score": float(article.style_score or 0),
            "risk_level": article.risk_level,
            "status": article.status,
            "created_at": str(article.created_at) if article.created_at else None,
        }


@router.post("/batch/{batch_type}")
async def run_batch(batch_type: str = "morning"):
    """手动触发批次任务（morning/noon/evening）。"""
    if batch_type not in ("morning", "noon", "evening"):
        raise HTTPException(status_code=400, detail="batch_type 必须是 morning/noon/evening")
    results = await pipeline.run_batch(batch_type)
    return {"batch_type": batch_type, "results": results}
