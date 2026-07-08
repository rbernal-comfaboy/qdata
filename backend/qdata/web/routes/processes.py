import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from qdata.auth.dependencies import get_current_user
from qdata.core.loader import load_data
from qdata.db.models import Project, Report, ScheduledTask, User
from qdata.db.session import async_session_factory, get_session
from qdata.web.routes.analyze import run_analysis_background

router = APIRouter()


class UpdateProcessRequest(BaseModel):
    name: str | None = None
    source_config: dict | None = None
    rules_config: list[str] | None = None


@router.get("/")
async def list_processes(
    group_id: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    def _extract_names(sc: dict | None):
        if not sc:
            return None, None
        st = sc.get("source_type") or ""
        cs = sc.get("connection_string") or ""
        fp = sc.get("file_path") or ""
        query = sc.get("query") or ""
        import re as _re
        table_name = None
        if query:
            m = _re.search(r"FROM\s+[`\"']?(\w+)[`\"']?", query, _re.IGNORECASE)
            if m:
                table_name = m.group(1).upper()
        if st in ("mysql", "postgresql", "sqlite", "mssql"):
            source_label = table_name or st.upper()
            db_name = cs.rsplit("/", 1)[-1].split("?")[0] if "/" in cs else None
            connection_label = db_name.upper() if db_name else cs
        elif st == "file":
            source_label = "Archivo"
            connection_label = fp.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if fp else None
        else:
            source_label = st.upper() if st else None
            m = _re.search(r"(?:DATABASE|Database)=([^;]+)", cs)
            db_name = m.group(1).upper() if m else None
            if not db_name:
                db_name = cs.rsplit("/", 1)[-1].split("?")[0] if "/" in cs else None
            connection_label = db_name or cs or fp or None
        return source_label, connection_label

    query = select(Project).where(Project.user_id == user.id)
    if group_id:
        query = query.where(Project.group_id == group_id)
    result = await session.execute(query.order_by(desc(Project.created_at)))
    projects = result.scalars().all()
    out = []
    for p in projects:
        report_result = await session.execute(
            select(Report).where(Report.project_id == p.id).order_by(desc(Report.executed_at)).limit(1)
        )
        latest = report_result.scalar_one_or_none()
        task_result = await session.execute(
            select(ScheduledTask).where(ScheduledTask.project_id == p.id).limit(1)
        )
        task = task_result.scalar_one_or_none()
        sl, cl = _extract_names(p.source_config)
        out.append({
            "id": str(p.id),
            "name": p.name,
            "status": p.status or "completed",
            "progress": p.progress,
            "source_config": p.source_config,
            "rules_config": p.rules_config,
            "source_label": sl,
            "connection_label": cl,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "latest_report": {
                "id": str(latest.id),
                "score": latest.score,
                "label": latest.label,
                "executed_at": latest.executed_at.isoformat() if latest.executed_at else None,
            } if latest else None,
            "scheduled_task": {
                "id": str(task.id),
                "name": task.name,
                "cron_expr": task.cron_expr,
                "status": task.status,
            } if task else None,
        })
    return out


@router.get("/{process_id}")
async def get_process(
    process_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(Project.id == process_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Process not found")

    reports_result = await session.execute(
        select(Report).where(Report.project_id == project.id).order_by(desc(Report.executed_at))
    )
    reports = reports_result.scalars().all()

    tasks_result = await session.execute(
        select(ScheduledTask).where(ScheduledTask.project_id == project.id)
    )
    tasks = tasks_result.scalars().all()

    return {
        "id": str(project.id),
        "name": project.name,
        "status": project.status or "completed",
        "progress": project.progress,
        "source_config": project.source_config,
        "rules_config": project.rules_config,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        "reports": [
            {
                "id": str(r.id),
                "score": r.score,
                "label": r.label,
                "result": r.result_json,
                "recommendations": r.recommendations,
                "summary": r.summary,
                "executed_at": r.executed_at.isoformat() if r.executed_at else None,
            }
            for r in reports
        ],
        "scheduled_tasks": [
            {
                "id": str(t.id),
                "name": t.name,
                "cron_expr": t.cron_expr,
                "timezone": t.timezone,
                "notify_emails": t.notify_emails,
                "notify_attach_report": t.notify_attach_report,
                "status": t.status,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "next_run": t.next_run.isoformat() if t.next_run else None,
            }
            for t in tasks
        ],
    }


@router.put("/{process_id}")
async def update_process(
    process_id: str,
    req: UpdateProcessRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(Project.id == process_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Process not found")

    if req.name is not None:
        project.name = req.name
    if req.source_config is not None:
        project.source_config = req.source_config
    if req.rules_config is not None:
        project.rules_config = req.rules_config

    await session.commit()
    return {"ok": True}


@router.delete("/{process_id}")
async def delete_process(
    process_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(Project.id == process_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Process not found")
    await session.delete(project)
    await session.commit()
    return {"ok": True}


@router.post("/{process_id}/pause")
async def pause_process(
    process_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(Project.id == process_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Process not found")
    if project.status != "running":
        raise HTTPException(status_code=400, detail="Solo se puede pausar un proceso en ejecución")
    project.status = "paused"
    prog = dict(project.progress or {})
    prog["status"] = "paused"
    project.progress = prog
    await session.commit()
    return {"status": "paused"}


@router.post("/{process_id}/resume")
async def resume_process(
    process_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(Project.id == process_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Process not found")
    if project.status != "paused":
        raise HTTPException(status_code=400, detail="Solo se puede reanudar un proceso en pausa")
    project.status = "running"
    prog = dict(project.progress or {})
    prog["status"] = "running"
    project.progress = prog
    await session.commit()
    return {"status": "running"}


@router.post("/{process_id}/stop")
async def stop_process(
    process_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(Project.id == process_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Process not found")
    if project.status not in ("running", "paused"):
        raise HTTPException(status_code=400, detail="Solo se puede detener un proceso en ejecución o pausa")
    prog = dict(project.progress or {})
    prog["skip_requested"] = True
    if project.status == "paused":
        project.status = "running"
        prog["status"] = "running"
    project.progress = prog
    await session.commit()
    return {"status": project.status}


@router.post("/{process_id}/rerun")
async def rerun_process(
    process_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(Project.id == process_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Process not found")

    sc = project.source_config
    st = sc.get("source_type", "")
    cs = sc.get("connection_string", "")
    q = sc.get("query", "")
    fp = sc.get("file_path", "")

    df = load_data(st, cs, q, fp)
    if df.empty:
        raise HTTPException(status_code=400, detail="No data loaded")

    selected_columns = sc.get("selected_columns")
    if selected_columns:
        sel = [c for c in selected_columns if c in df.columns]
        if sel:
            df = df[sel]

    project.status = "running"
    project.progress = {
        "total": 0, "completed": 0, "current": 0, "current_rule": "",
        "status": "running", "score": None, "label": None, "report_id": None, "rules": [],
    }
    await session.commit()

    asyncio.create_task(run_analysis_background(
        project_id=project.id,
        df=df,
        rules_config=project.rules_config,
        user_id=user.id,
        rule_configs={},
    ))

    return {"status": "running", "project_id": str(project.id)}
