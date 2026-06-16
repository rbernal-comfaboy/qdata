import asyncio
import datetime
import json
import math
from decimal import Decimal
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from qdata.auth.dependencies import get_current_user, get_user_or_token
from qdata.core.engine import Engine, resolve_rules
from qdata.core.loader import load_data
from qdata.core.reporter import generate_json_report
from qdata.core.score import build_recommendations, calculate_score
from qdata.db.models import Project, Report, Source, DataSource, User
from qdata.db.session import async_session_factory, get_session
from qdata.rules.base import RuleResult

router = APIRouter()


def _safe_val(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return bool(v)
    if isinstance(v, (int, float)):
        if math.isinf(v) or math.isnan(v):
            return str(v)
        return int(v) if isinstance(v, (int, bool)) else float(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, datetime.timedelta):
        return v.total_seconds()
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return {k: _safe_val(v) for k, v in v.items()}
    if isinstance(v, (list, tuple)):
        return [_safe_val(x) for x in v]
    try:
        if pd.isna(v):
            return None
    except (ValueError, TypeError):
        pass
    if hasattr(v, "item"):
        try:
            return _safe_val(v.item())
        except (ValueError, TypeError):
            return str(v)
    try:
        json.dumps(v)
        return v
    except (TypeError, OverflowError):
        return str(v)


class AnalyzeRequest(BaseModel):
    project_name: str
    source_id: str = ""
    source_type: str = ""
    connection_string: str = ""
    query: str = ""
    file_path: str = ""
    rules: list[str] = ["nullity", "duplicates", "types", "ranges"]
    columns: list[str] | None = None


class AnalyzeResponse(BaseModel):
    report_id: str | None = None
    project_id: str | None = None
    score: int
    label: str
    rules_count: int
    recommendations: list[dict]


@router.post("/", response_model=AnalyzeResponse)
async def run_analysis(
    req: AnalyzeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    st = req.source_type
    cs = req.connection_string
    q = req.query
    fp = req.file_path

    if req.source_id:
        result = await session.execute(
            select(Source).where(Source.id == req.source_id, Source.user_id == user.id)
        )
        s = result.scalar_one_or_none()
        if not s:
            raise HTTPException(status_code=404, detail="Source not found")
        ds = await session.get(DataSource, s.data_source_id)
        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")
        st = ds.source_type
        cs = ds.connection_string or ""
        q = s.query or ""
        fp = ds.file_path or ""

    try:
        kwargs = {}
        if req.source_id and s.row_limit:
            kwargs["nrows"] = s.row_limit
        if req.source_id:
            kwargs["storage_mode"] = s.storage_mode or "memory"
        df = load_data(st, cs, q, fp, **kwargs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error loading data: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="No data loaded")

    if req.columns:
        missing = [c for c in req.columns if c not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"Columns not found: {missing}")
        df = df[[c for c in req.columns if c in df.columns]]
    elif req.source_id and s.selected_columns:
        sel = [c for c in s.selected_columns if c in df.columns]
        if sel:
            df = df[sel]

    engine = Engine(parallel=False)
    rules = resolve_rules(req.rules)
    results = await engine.run(df, rules)

    score, label = calculate_score(results)
    recommendations = build_recommendations(results)

    total_duration = round(sum(r.duration_ms for r in results), 2)

    project = Project(
        user_id=user.id,
        name=req.project_name,
        source_config={
            "source_type": st,
            "connection_string": cs,
            "query": q,
            "file_path": fp,
        },
        rules_config=req.rules,
        status="completed",
    )
    session.add(project)
    await session.flush()

    report = Report(
        project_id=project.id,
        user_id=user.id,
        score=score,
        label=label,
        result_json=_safe_val({
            "results": [r.__dict__ for r in results],
            "recommendations": recommendations,
        }),
        recommendations=recommendations,
        summary=f"Score: {score}/100 ({label}). Reglas ejecutadas: {len(results)}. Duración: {total_duration}ms.",
    )
    session.add(report)
    await session.commit()

    return AnalyzeResponse(
        report_id=str(report.id),
        project_id=str(project.id),
        score=score,
        label=label,
        rules_count=len(results),
        recommendations=recommendations,
    )


def _safe_rules(rules: list[dict]) -> list[dict]:
    return [_safe_val(r) for r in rules]


def _save_progress(project, rules_progress: list[dict], **kw):
    project.progress = {
        "total": kw.get("total", 0),
        "completed": kw.get("completed", 0),
        "current": kw.get("current", 0),
        "current_rule": kw.get("current_rule", ""),
        "status": kw.get("status", "running"),
        "score": kw.get("score"),
        "label": kw.get("label"),
        "report_id": kw.get("report_id"),
        "rules": _safe_rules(rules_progress),
    }


async def run_analysis_background(
    project_id: Any,
    df: pd.DataFrame,
    rules_config: list[str] | str,
    user_id: Any,
):
    """Background task: runs rules sequentially, updates progress after each rule.

    Optimized with DataCube: makes ONE shared copy of the DataFrame (instead of one per rule)
    so large datasets with many rules use drastically less memory.
    """
    import logging
    import time
    logger = logging.getLogger("qdata.analyze.background")
    try:
        async with async_session_factory() as session:
            project = await session.get(Project, project_id)
            if not project:
                logger.error("Project %s not found", project_id)
                return
            rules = resolve_rules(rules_config)
            total = len(rules)
            rules_progress = [
                {"name": r.name, "label": r.description[:60] if r.description else r.name, "status": "pending"}
                for r in rules
            ]
            project.status = "running"
            _save_progress(project, rules_progress, total=total, status="running")
            await session.commit()

            # Create DuckDB connection so NullCheck/RangeCheck use SQL paths
            extra = {}
            try:
                import duckdb
                duckdb_conn = duckdb.connect(":memory:")
                duckdb_conn.register("data", df)
                extra["duckdb_conn"] = duckdb_conn
            except ImportError:
                duckdb_conn = None

            # Single shared copy — rules run sequentially so no race conditions
            shared_df = df.copy()

            results = []
            total_start = time.perf_counter()
            loop_error = None
            for i, rule in enumerate(rules):
                await session.refresh(project)
                # Before rule: skip_requested → skip this rule, reset flag
                prog = dict(project.progress or {})
                if prog.pop("skip_requested", False):
                    logger.info("Skipping rule %d/%d (skip requested before execution)", i + 1, total)
                    rules_progress[i]["status"] = "skipped"
                    project.progress = dict(prog)
                    _save_progress(project, rules_progress, total=total, completed=i, current=i, current_rule="",
                                   status="running")
                    await session.commit()
                    continue
                # Before rule: paused → wait for resume or skip
                if project.status == "paused":
                    rules_progress[i]["status"] = "paused"
                    _save_progress(project, rules_progress, total=total, completed=i, current=i, current_rule=rule.name,
                                   status="paused")
                    await session.commit()
                    while True:
                        await asyncio.sleep(2)
                        await session.refresh(project)
                        if project.status == "running":
                            break
                        prog = dict(project.progress or {})
                        if prog.pop("skip_requested", False):
                            logger.info("Skipping rule %d/%d (skip requested while paused)", i + 1, total)
                            rules_progress[i]["status"] = "skipped"
                            project.status = "running"
                            project.progress = dict(prog)
                            _save_progress(project, rules_progress, total=total, completed=i, current=i, current_rule="",
                                           status="running")
                            await session.commit()
                            break
                    if project.status != "running" or rules_progress[i].get("status") == "skipped":
                        continue

                rules_progress[i]["status"] = "running"
                _save_progress(project, rules_progress, total=total, completed=i, current=i + 1, current_rule=rule.name, status="running")
                await session.commit()
                logger.info("Executing rule %d/%d: %s", i + 1, total, rule.name)
                t0 = time.perf_counter()
                try:
                    result = await asyncio.get_event_loop().run_in_executor(None, rule.execute, shared_df, **extra)
                    result.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                    # After execution: skip_requested during rule → discard result
                    await session.refresh(project)
                    prog = dict(project.progress or {})
                    if prog.pop("skip_requested", False):
                        logger.info("Discarding result of rule %d/%s (skip requested during execution)", i + 1, rule.name)
                        rules_progress[i]["status"] = "skipped"
                        project.progress = dict(prog)
                        _save_progress(project, rules_progress, total=total, completed=i + 1, current=i + 1, current_rule=rule.name, status="running")
                        await session.commit()
                        continue
                    results.append(result)
                    rules_progress[i]["status"] = "done"
                    rules_progress[i]["passed"] = result.passed
                    rules_progress[i]["failed"] = result.failed
                    _save_progress(project, rules_progress, total=total, completed=i + 1, current=i + 1, current_rule=rule.name, status="running")
                except Exception as e:
                    logger.exception("Rule %s failed: %s", rule.name, e)
                    elapsed = round((time.perf_counter() - t0) * 1000, 2)
                    # After failure: skip_requested during rule → discard error result
                    await session.refresh(project)
                    prog = dict(project.progress or {})
                    if prog.pop("skip_requested", False):
                        logger.info("Discarding failed result of rule %d/%s (skip requested during execution)", i + 1, rule.name)
                        rules_progress[i]["status"] = "skipped"
                        project.progress = dict(prog)
                        _save_progress(project, rules_progress, total=total, completed=i + 1, current=i + 1, current_rule=rule.name, status="running")
                        await session.commit()
                        continue
                    results.append(RuleResult(
                        rule_name=rule.name, description=rule.description, severity=rule.severity,
                        passed=False, total=0, failed=0, failure_pct=0,
                        details=[{"error": str(e)}], recommendation=f"Error: {e}",
                        duration_ms=elapsed,
                    ))
                    rules_progress[i]["status"] = "failed"
                    rules_progress[i]["error"] = str(e)
                    _save_progress(project, rules_progress, total=total, completed=i + 1, current=i + 1, current_rule=rule.name, status="running")
                await session.commit()

            if duckdb_conn is not None:
                try:
                    duckdb_conn.close()
                except Exception:
                    pass

            total_duration = round((time.perf_counter() - total_start) * 1000, 2)
            score, label = calculate_score(results)
            recommendations = build_recommendations(results)
            safe_results = _safe_val({"results": [r.__dict__ for r in results], "recommendations": recommendations})
            report = Report(
                project_id=project.id, user_id=user_id,
                score=score, label=label,
                result_json=safe_results,
                recommendations=recommendations,
                summary=f"Score: {score}/100 ({label}). Reglas ejecutadas: {len(results)}. Duración: {total_duration}ms.",
            )
            session.add(report)
            await session.flush()
            project.status = "completed"
            _save_progress(project, rules_progress, total=total, completed=total, current=total,
                           status="completed", score=score, label=label, report_id=str(report.id))
            await session.commit()
            logger.info("Analysis complete: project=%s score=%d duration=%.0fms", project_id, score, total_duration)
    except Exception as e:
        logger.exception("Background analysis crashed: %s", e)
        loop_error = str(e)
        try:
            async with async_session_factory() as s:
                 p = await s.get(Project, project_id)
                 if p:
                     p.status = "failed"
                     prog = dict(p.progress or {})
                     prog["status"] = "failed"
                     prog["error"] = loop_error
                     p.progress = prog
                     await s.commit()
        except Exception:
            pass


@router.post("/start")
async def start_analysis(
    req: AnalyzeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    st = req.source_type
    cs = req.connection_string
    q = req.query
    fp = req.file_path

    if req.source_id:
        result = await session.execute(
            select(Source).where(Source.id == req.source_id, Source.user_id == user.id)
        )
        s = result.scalar_one_or_none()
        if not s:
            raise HTTPException(status_code=404, detail="Source not found")
        ds = await session.get(DataSource, s.data_source_id)
        if not ds:
            raise HTTPException(status_code=404, detail="Data source not found")
        st = ds.source_type
        cs = ds.connection_string or ""
        q = s.query or ""
        fp = ds.file_path or ""

    try:
        kwargs = {}
        if req.source_id and s.row_limit:
            kwargs["nrows"] = s.row_limit
        if req.source_id:
            kwargs["storage_mode"] = s.storage_mode or "memory"
        df = load_data(st, cs, q, fp, **kwargs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error loading data: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="No data loaded")

    if req.columns:
        missing = [c for c in req.columns if c not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"Columns not found: {missing}")
        df = df[[c for c in req.columns if c in df.columns]]
    elif req.source_id and s.selected_columns:
        sel = [c for c in s.selected_columns if c in df.columns]
        if sel:
            df = df[sel]

    project = Project(
        user_id=user.id,
        name=req.project_name or f"Análisis",
        source_config={
            "source_type": st,
            "connection_string": cs,
            "query": q,
            "file_path": fp,
        },
        rules_config=req.rules,
        status="pending",
        progress={
            "total": 0,
            "completed": 0,
            "current": 0,
            "current_rule": "",
            "status": "pending",
            "score": None,
            "label": None,
            "report_id": None,
            "rules": [],
        },
    )
    session.add(project)
    await session.commit()

    asyncio.create_task(run_analysis_background(
        project_id=project.id,
        df=df,
        rules_config=req.rules,
        user_id=user.id,
    ))

    return {"project_id": str(project.id), "status": "pending"}


@router.get("/cube-stats")
async def get_cube_stats():
    """Returns DataCube memory and cache statistics for monitoring."""
    try:
        from qdata.core.cube import DataCubeManager
        cube_mgr = DataCubeManager.get_instance()
        return cube_mgr.get_stats()
    except ImportError:
        return {"cubes": 0, "total_rows": 0, "total_memory_mb": 0, "max_memory_mb": 0, "error": "duckdb not installed"}


@router.get("/{project_id}/stream")
async def stream_analysis_progress(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_user_or_token),
):
    result = await session.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    async def event_stream():
        while True:
            q = await session.execute(
                select(Project).where(Project.id == project_id)
            )
            p = q.scalar_one_or_none()
            if not p:
                yield f"event: error\ndata: {json.dumps({'error': 'Project not found'})}\n\n"
                return

            progress = p.progress or {
                "status": "pending",
                "total": 0,
                "completed": 0,
                "current": 0,
                "current_rule": "",
                "score": None,
                "label": None,
                "report_id": None,
                "rules": [],
            }
            progress["project_id"] = str(p.id)
            progress["project_name"] = p.name

            yield f"event: progress\ndata: {json.dumps(progress)}\n\n"

            status = p.status or progress.get("status")
            if status in ("completed", "failed"):
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
