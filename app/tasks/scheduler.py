import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import List, Optional

logger = logging.getLogger("autowz.scheduler")

_scheduler: Optional[AsyncIOScheduler] = None


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


async def _job_batch(batch_type: str, count: int = 1, module_name: Optional[str] = None):
    """定时任务：执行模块批次。"""
    from app.services.pipeline import ArticlePipeline

    logger.info("定时任务: 开始批次 %s module=%s count=%s", batch_type, module_name, count)
    pipeline = ArticlePipeline(module_name)
    try:
        results = await pipeline.run_batch(batch_type, count=count)
        logger.info("批次 %s/%s 完成: %d 篇", module_name, batch_type, len(results))
    except Exception as exc:
        logger.error("批次 %s/%s 失败: %s", module_name, batch_type, exc)


async def _job_sync_published():
    """定时任务：同步公众号「已发布」列表到本地，供导读区块使用。"""
    from app.services.wechat.publish_sync import sync_published_articles

    logger.info("定时任务: 同步公众号已发布文章")
    try:
        result = await sync_published_articles()
        if result.get("auth_expired"):
            logger.error("同步失败 - 登录凭据已过期，请到 newwz 重新扫码: %s", result.get("error"))
        else:
            logger.info("同步完成: %s", result)
    except Exception as exc:
        logger.error("同步任务异常: %s", exc)


def init_scheduler() -> AsyncIOScheduler:
    """初始化并启动定时调度器。

    发文任务来自 ACTIVE_MODULE 对应模块的 schedule_slots。
    默认 ACTIVE_MODULE=entertainment，因此当前默认跑娱乐模块。
    """
    from app.modules.registry import get_module, resolve_module_name

    scheduler = get_scheduler()

    # 热点采集:每30分钟
    scheduler.add_job(
        _job_collect,
        CronTrigger(minute="*/30"),
        id="collect_hot_topics",
        replace_existing=True,
    )

    module_name = resolve_module_name()
    module = get_module(module_name)
    for slot in module.schedule_slots:
        job_id = f"batch_{module_name}_{slot.batch_type}"
        scheduler.add_job(
            _job_batch,
            CronTrigger(hour=slot.hour, minute=slot.minute),
            args=[slot.batch_type, slot.count, module_name],
            id=job_id,
            replace_existing=True,
        )
        logger.info(
            "注册模块定时任务: id=%s module=%s time=%02d:%02d count=%d",
            job_id,
            module_name,
            slot.hour,
            slot.minute,
            slot.count,
        )

    # 公众号已发布文章同步:每日 03:17(避开整点降低风控,凌晨流量低)
    scheduler.add_job(
        _job_sync_published,
        CronTrigger(hour=3, minute=17),
        id="sync_published_articles",
        replace_existing=True,
    )

    if not scheduler.running:
        scheduler.start()
    jobs = scheduler.get_jobs()
    logger.info("调度器已启动,共 %d 个定时任务", len(jobs))
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


def get_scheduler_status() -> List[dict]:
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
