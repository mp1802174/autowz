import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("autowz.scheduler")

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    return _scheduler


async def _job_collect():
    """定时任务：采集热点。"""
    from app.services.pipeline import ArticlePipeline
    logger.info("定时任务: 开始采集热点")
    pipeline = ArticlePipeline()
    try:
        saved = await pipeline.collect_topics()
        logger.info("定时采集完成: %d 条", len(saved))
    except Exception as exc:
        logger.error("定时采集失败: %s", exc)


async def _job_batch(batch_type: str):
    """定时任务：执行批次。"""
    from app.services.pipeline import ArticlePipeline
    logger.info("定时任务: 开始批次 %s", batch_type)
    pipeline = ArticlePipeline()
    try:
        results = await pipeline.run_batch(batch_type)
        logger.info("批次 %s 完成: %d 篇", batch_type, len(results))
    except Exception as exc:
        logger.error("批次 %s 失败: %s", batch_type, exc)


def init_scheduler() -> AsyncIOScheduler:
    """初始化并启动定时调度器。"""
    scheduler = get_scheduler()

    # 热点采集：每30分钟
    scheduler.add_job(
        _job_collect, CronTrigger(minute="*/30"),
        id="collect_hot_topics", replace_existing=True,
    )

    # 早间批次：07:05 生成短文1
    scheduler.add_job(
        _job_batch, CronTrigger(hour=7, minute=5),
        args=["morning"], id="morning_batch", replace_existing=True,
    )

    # 午间批次：12:05 生成短文2
    scheduler.add_job(
        _job_batch, CronTrigger(hour=12, minute=5),
        args=["noon"], id="noon_batch", replace_existing=True,
    )

    # 晚间批次：18:35 生成长文
    scheduler.add_job(
        _job_batch, CronTrigger(hour=18, minute=35),
        args=["evening"], id="evening_batch", replace_existing=True,
    )

    scheduler.start()
    jobs = scheduler.get_jobs()
    logger.info("调度器已启动，共 %d 个定时任务", len(jobs))
    for job in jobs:
        logger.info("  任务: %s, 下次执行: %s", job.id, job.next_run_time)
    return scheduler


def shutdown_scheduler() -> None:
    """停止调度器。"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("调度器已停止")
    _scheduler = None


def get_scheduler_status() -> list[dict]:
    """获取当前所有定时任务的状态。"""
    scheduler = get_scheduler()
    return [
        {
            "id": job.id,
            "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        for job in scheduler.get_jobs()
    ]
