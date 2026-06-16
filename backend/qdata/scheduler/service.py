import logging
from datetime import datetime, timezone

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from qdata.core.config import settings
from qdata.core.engine import Engine
from qdata.core.loader import load_data
from qdata.core.score import build_recommendations, calculate_score
from qdata.db.models import DataSource, ScheduledTask, Source, TaskHistory
from qdata.db.session import async_session_factory

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)


async def run_scheduled_task(task_id: str):
    logger.info(f"Running scheduled task {task_id}")
    async with async_session_factory() as session:
        result = await session.execute(select(ScheduledTask).where(ScheduledTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        history = TaskHistory(task_id=task.id, status="running")
        session.add(history)
        await session.commit()
        await session.refresh(history)

        try:
            sc = task.project.source_config or {}
            st = sc.get("source_type", "")
            cs = sc.get("connection_string", "")
            q = sc.get("query", "")
            fp = sc.get("file_path", "")
            df = load_data(st, cs, q, fp)

            engine = Engine(parallel=True)
            rules = task.project.rules_config if isinstance(task.project.rules_config, list) else ["nullity", "duplicates", "types"]
            results = await engine.run(df, rules)
            score, label = calculate_score(results)
            recommendations = build_recommendations(results)

            history.status = "success"
            history.score = score
            history.finished_at = datetime.now(timezone.utc)
            await session.commit()

            if task.notify_emails:
                from qdata.scheduler.notifier import send_quality_report
                summary = f"Score: {score}/100. Ejecutadas {len(results)} reglas."
                await send_quality_report(
                    to_emails=list(task.notify_emails),
                    task_name=task.name,
                    score=score,
                    label=label,
                    summary=summary,
                )
                history.email_sent = True
                await session.commit()

            task.last_run = datetime.now(timezone.utc)
            task.error_count = 0
            await session.commit()

        except Exception as e:
            logger.exception(f"Task {task_id} failed")
            history.status = "failed"
            history.error = str(e)
            history.finished_at = datetime.now(timezone.utc)
            task.error_count = (task.error_count or 0) + 1
            await session.commit()


async def refresh_source_cube(source_id: str):
    """Refresh the DuckDB cube for a memory-mode source."""
    logger.info(f"Refreshing cube for source {source_id}")
    try:
        async with async_session_factory() as session:
            s = await session.get(Source, source_id)
            if not s or s.storage_mode != "memory":
                logger.info("Source %s not found or not memory mode, skipping", source_id)
                return
            ds = await session.get(DataSource, s.data_source_id)
            if not ds:
                logger.warning("DataSource not found for source %s", source_id)
                return
            load_data(ds.source_type, ds.connection_string or "", s.query or "", ds.file_path or "", storage_mode="memory")
            logger.info("Cube refreshed for source %s", source_id)
    except Exception as e:
        logger.exception("Failed to refresh cube for source %s: %s", source_id, e)


async def add_source_refresh_job(source_id: str, cron_expr: str):
    """Register a cron job to periodically refresh a source's cube."""
    trigger = CronTrigger.from_crontab(cron_expr)
    scheduler.add_job(
        refresh_source_cube,
        trigger=trigger,
        id=f"source_refresh_{source_id}",
        args=[source_id],
        replace_existing=True,
    )
    logger.info(f"Scheduled cube refresh for source {source_id}: {cron_expr}")


async def remove_source_refresh_job(source_id: str):
    """Unregister the cron job for a source's cube refresh."""
    job_id = f"source_refresh_{source_id}"
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Removed cube refresh job for source {source_id}")
    except Exception:
        pass


async def add_scheduled_task(task: ScheduledTask):
    trigger = CronTrigger.from_crontab(task.cron_expr)
    scheduler.add_job(
        run_scheduled_task,
        trigger=trigger,
        id=str(task.id),
        args=[str(task.id)],
        replace_existing=True,
    )
    logger.info(f"Scheduled task {task.id}: {task.cron_expr}")


async def remove_scheduled_task(task_id: str):
    try:
        scheduler.remove_job(task_id)
    except JobLookupError:
        logger.warning(f"Job {task_id} not found in scheduler (may have been lost on restart)")
    logger.info(f"Removed task {task_id}")


async def pause_scheduled_task(task_id: str):
    scheduler.pause_job(task_id)


async def resume_scheduled_task(task_id: str):
    scheduler.resume_job(task_id)


def start_scheduler():
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
