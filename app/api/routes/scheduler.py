from fastapi import APIRouter, HTTPException

from app.tasks.scheduler import get_scheduler_status, get_scheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status")
async def scheduler_status():
    """查看调度器中所有定时任务的状态。"""
    return {"jobs": get_scheduler_status()}


@router.post("/trigger/{job_id}")
async def trigger_job(job_id: str):
    """手动触发指定的定时任务。"""
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"任务不存在: {job_id}")
    job.modify(next_run_time=None)  # 立即执行
    scheduler.wakeup()
    return {"message": f"任务 {job_id} 已触发"}
