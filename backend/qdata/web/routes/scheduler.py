import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from qdata.auth.dependencies import get_current_user
from qdata.auth.permissions import require_role
from qdata.db.models import Project, ScheduledTask, TaskHistory, User
from qdata.db.session import get_session
from qdata.scheduler.service import (
    add_scheduled_task,
    pause_scheduled_task as pause_task,
    remove_scheduled_task,
    resume_scheduled_task as resume_task,
    run_scheduled_task,
)

router = APIRouter()


class TaskCreate(BaseModel):
    project_id: str
    name: str
    cron_expr: str
    timezone: str = "UTC"
    notify_emails: list[str] = []
    notify_attach_report: bool = True


class TaskUpdate(BaseModel):
    name: str | None = None
    cron_expr: str | None = None
    notify_emails: list[str] | None = None


@router.post("/tasks")
async def create_task(
    req: TaskCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(Project.id == req.project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = ScheduledTask(
        id=uuid.uuid4(),
        project_id=project.id,
        user_id=user.id,
        name=req.name,
        cron_expr=req.cron_expr,
        timezone=req.timezone,
        notify_emails=req.notify_emails,
        notify_attach_report=req.notify_attach_report,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    await add_scheduled_task(task)

    return {
        "id": str(task.id),
        "name": task.name,
        "cron_expr": task.cron_expr,
        "next_run": task.next_run.isoformat() if task.next_run else None,
    }


@router.get("/tasks")
async def list_tasks(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ScheduledTask).where(ScheduledTask.user_id == user.id)
    )
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "cron_expr": t.cron_expr,
            "status": t.status,
            "last_run": t.last_run.isoformat() if t.last_run else None,
            "next_run": t.next_run.isoformat() if t.next_run else None,
            "error_count": t.error_count,
        }
        for t in tasks
    ]


@router.delete("/tasks")
async def delete_all_tasks(
    user: User = Depends(require_role(["admin"])),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(ScheduledTask))
    tasks = result.scalars().all()
    for task in tasks:
        await remove_scheduled_task(str(task.id))
        await session.delete(task)
    await session.commit()
    return {"status": "deleted", "count": len(tasks)}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    user: User = Depends(require_role(["admin"])),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(ScheduledTask).where(ScheduledTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await remove_scheduled_task(task_id)
    await session.delete(task)
    await session.commit()
    return {"status": "deleted"}


@router.post("/tasks/{task_id}/pause")
async def pause_task_endpoint(
    task_id: str,
    user: User = Depends(get_current_user),
):
    await pause_task(task_id)
    return {"status": "paused"}


@router.post("/tasks/{task_id}/resume")
async def resume_task_endpoint(
    task_id: str,
    user: User = Depends(get_current_user),
):
    await resume_task(task_id)
    return {"status": "resumed"}


@router.post("/tasks/{task_id}/run")
async def run_task_now(
    task_id: str,
    user: User = Depends(get_current_user),
):
    await run_scheduled_task(task_id)
    return {"status": "triggered"}


@router.get("/tasks/{task_id}/history")
async def task_history(
    task_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ScheduledTask).where(ScheduledTask.id == task_id, ScheduledTask.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    history_result = await session.execute(
        select(TaskHistory)
        .where(TaskHistory.task_id == task_id)
        .order_by(TaskHistory.started_at.desc())
        .limit(50)
    )
    return [
        {
            "id": str(h.id),
            "status": h.status,
            "score": h.score,
            "error": h.error,
            "email_sent": h.email_sent,
            "started_at": h.started_at.isoformat() if h.started_at else None,
            "finished_at": h.finished_at.isoformat() if h.finished_at else None,
        }
        for h in history_result.scalars().all()
    ]
