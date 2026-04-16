from fastapi import APIRouter

from app.api.routes.articles import router as articles_router
from app.api.routes.health import router as health_router
from app.api.routes.scheduler import router as scheduler_router
from app.core.config import get_settings


settings = get_settings()

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(articles_router, prefix=settings.api_prefix)
api_router.include_router(scheduler_router, prefix=settings.api_prefix)
