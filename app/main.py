import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.engine import init_db
from app.tasks.scheduler import init_scheduler, shutdown_scheduler

logger = logging.getLogger("autowz")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    setup_logging()
    logger.info("初始化数据库...")
    init_db()
    logger.info("启动定时调度器...")
    init_scheduler()
    logger.info("Autowz 服务启动完成")
    yield
    # 关闭
    logger.info("正在关闭...")
    shutdown_scheduler()


settings = get_settings()

app = FastAPI(
    title="今天怎么看 - 自动微信公众号文章发布系统",
    version="0.1.0",
    debug=settings.app_debug,
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {
        "app": settings.app_name,
        "env": settings.app_env,
        "message": "Autowz service is running.",
    }
