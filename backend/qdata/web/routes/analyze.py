import asyncio
import datetime
import json
import math
import threading
from decimal import Decimal
from functools import partial
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
        v = float(v)
        return round(v, 6) if v != int(v) else int(v)
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
    rule_configs: dict[str, dict[str, Any]] = {}
    group_id: str | None = None


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
    rules = resolve_rules(req.rules, req.rule_configs)
    results = await engine.run(df, rules)

    score, label = calculate_score(results)
    recommendations = build_recommendations(results)

    total_duration = round(sum(r.duration_ms for r in results), 2)

    source_config = {
        "source_type": st,
        "connection_string": cs,
        "query": q,
        "file_path": fp,
    }
    if req.columns:
        source_config["selected_columns"] = req.columns
    elif req.source_id and s.selected_columns:
        source_config["selected_columns"] = s.selected_columns

    project = Project(
        user_id=user.id,
        group_id=req.group_id,
        name=req.project_name,
        source_config=source_config,
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


class _RuleProgress:
    """Thread-safe holder for intra-rule progress + log messages."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.processed = 0
        self.total = 1
        self.message = ""
        self.phase = ""
        self.extra: dict[str, Any] = {}
        self.logs: list[str] = []
        self.dirty = False

    def callback(self, processed: int, total: int, message: str, phase: str = "", extra: dict[str, Any] | None = None) -> None:
        with self.lock:
            self.processed = processed
            self.total = total if total > 0 else 1
            self.message = message
            self.dirty = True
            if phase:
                self.phase = phase
            self.extra = dict(extra) if extra else {}

    def append_log(self, msg: str) -> None:
        with self.lock:
            self.logs.append(msg)
            self.dirty = True


def _safe_rules(rules: list[dict]) -> list[dict]:
    return [_safe_val(r) for r in rules]


def _save_progress(project, rules_progress: list[dict], **kw):
    old = project.progress or {}
    project.progress = {
        "total": kw.get("total", 0),
        "completed": kw.get("completed", 0),
        "current": kw.get("current", 0),
        "current_rule": kw.get("current_rule", ""),
        "status": kw.get("status", "running"),
        "score": kw.get("score"),
        "label": kw.get("label"),
        "report_id": kw.get("report_id"),
        "total_records": _safe_val(kw.get("total_records")) if "total_records" in kw else old.get("total_records"),
        "records_processed": _safe_val(kw.get("records_processed")) if "records_processed" in kw else old.get("records_processed"),
        "rules": _safe_rules(rules_progress),
    }


async def load_and_analyze_background(
    project_id: Any,
    source_type: str,
    connection_string: str,
    query: str,
    file_path: str,
    load_kwargs: dict,
    columns: list[str] | None,
    selected_columns: list[str] | None,
    rules_config: list[str] | str,
    user_id: Any,
    rule_configs: dict[str, dict] | None = None,
):
    """Background task: loads data with progress, then runs analysis."""
    import logging
    logger = logging.getLogger("qdata.analyze.background")

    _last_progress = {"loaded": 0, "total": 0, "msg": "Iniciando carga de datos..."}
    _loading_done = False

    def _load_progress(loaded, total, msg):
        _last_progress["loaded"] = loaded
        _last_progress["total"] = total
        _last_progress["msg"] = msg

    try:
        async with async_session_factory() as session:
            project = await session.get(Project, project_id)
            if not project:
                return

            project.status = "loading"
            p = dict(project.progress or {})
            p["status"] = "loading"
            p["load_message"] = "Iniciando carga de datos..."
            p["records_loaded"] = 0
            p["total_records"] = 0
            project.progress = p
            await session.commit()

            load_task = asyncio.get_event_loop().run_in_executor(
                None,
                lambda: load_data(source_type, connection_string, query, file_path,
                                  progress_callback=_load_progress, **load_kwargs),
            )

            while not load_task.done():
                await asyncio.sleep(0.5)
                p = dict(project.progress or {})
                p["status"] = "loading"
                p["load_message"] = _last_progress["msg"]
                p["records_loaded"] = _last_progress["loaded"]
                p["total_records"] = _last_progress["total"]
                project.progress = p
                await session.commit()

            try:
                df = load_task.result()
            except Exception as e:
                logger.exception("Failed to load data for project %s", project_id)
                p = dict(project.progress or {})
                p["status"] = "failed"
                p["load_message"] = f"Error cargando datos: {e}"
                project.progress = p
                project.status = "failed"
                await session.commit()
                return

            if df.empty:
                p = dict(project.progress or {})
                p["status"] = "failed"
                p["load_message"] = "No se encontraron datos"
                project.progress = p
                project.status = "failed"
                await session.commit()
                return

            if columns:
                missing = [c for c in columns if c not in df.columns]
                if missing:
                    p = dict(project.progress or {})
                    p["status"] = "failed"
                    p["load_message"] = f"Columnas no encontradas: {missing}"
                    project.progress = p
                    project.status = "failed"
                    await session.commit()
                    return
                df = df[[c for c in columns if c in df.columns]]
            elif selected_columns:
                sel = [c for c in selected_columns if c in df.columns]
                if sel:
                    df = df[sel]

            p = dict(project.progress or {})
            p["load_message"] = f"Datos cargados: {len(df):,} registros"
            p["records_loaded"] = len(df)
            p["total_records"] = len(df)
            project.progress = p
            await session.commit()

    except Exception as e:
        logger.exception("load_and_analyze_background failed for project %s", project_id)
        try:
            async with async_session_factory() as session:
                project = await session.get(Project, project_id)
                if project:
                    p = dict(project.progress or {})
                    p["status"] = "failed"
                    p["load_message"] = f"Error: {e}"
                    project.progress = p
                    project.status = "failed"
                    await session.commit()
        except Exception:
            pass
        return

    await run_analysis_background(
        project_id=project_id,
        df=df,
        rules_config=rules_config,
        user_id=user_id,
        rule_configs=rule_configs,
    )


async def run_analysis_background(
    project_id: Any,
    df: pd.DataFrame,
    rules_config: list[str] | str,
    user_id: Any,
    rule_configs: dict[str, dict] | None = None,
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
            rules = resolve_rules(rules_config, rule_configs)
            total = len(rules)
            total_records = len(df)
            rules_progress = [
                {"name": r.name, "label": r.description[:60] if r.description else r.name, "status": "pending",
                 "rule_total_records": total_records, "rule_records_processed": 0}
                for r in rules
            ]
            project.status = "running"
            _save_progress(project, rules_progress, total=total, status="running", total_records=total_records)
            await session.commit()

            # Create DuckDB connection so NullCheck/RangeCheck use SQL paths
            extra = {}
            try:
                import duckdb
                duckdb_conn = duckdb.connect(":memory:")
                duckdb_conn.register("data", df)
                extra["duckdb_conn"] = duckdb_conn
            except Exception:
                duckdb_conn = None

            # Single shared copy — rules run sequentially so no race conditions
            shared_df = df.copy()

            def _cancel_remaining(from_idx: int):
                for j in range(from_idx, total):
                    if rules_progress[j]["status"] == "pending":
                        rules_progress[j]["status"] = "skipped"

            results = []
            total_start = time.perf_counter()
            records_processed = 0
            stopped = False
            loop_error = None
            for i, rule in enumerate(rules):
                await session.refresh(project)
                # Before rule: skip_requested → cancel all remaining, stop
                prog = dict(project.progress or {})
                if prog.pop("skip_requested", False):
                    logger.info("Cancelling analysis (stop requested before rule %d/%d)", i + 1, total)
                    rules_progress[i]["status"] = "skipped"
                    _cancel_remaining(i + 1)
                    project.progress = dict(prog)
                    _save_progress(project, rules_progress, total=total, completed=i, current=i, current_rule="",
                                   status="cancelled")
                    await session.commit()
                    stopped = True
                    break
                # Before rule: paused → wait for resume or cancel
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
                            logger.info("Cancelling analysis (stop requested while paused at rule %d/%d)", i + 1, total)
                            rules_progress[i]["status"] = "skipped"
                            _cancel_remaining(i + 1)
                            project.status = "cancelled"
                            project.progress = dict(prog)
                            _save_progress(project, rules_progress, total=total, completed=i, current=i, current_rule="",
                                           status="cancelled")
                            await session.commit()
                            stopped = True
                            break
                    if stopped:
                        break
                    if project.status != "running":
                        continue

                rules_progress[i]["status"] = "running"
                _save_progress(project, rules_progress, total=total, completed=i, current=i + 1, current_rule=rule.name, status="running")
                await session.commit()
                logger.info("Executing rule %d/%d: %s", i + 1, total, rule.name)
                t0 = time.perf_counter()
                try:
                    rp = _RuleProgress()
                    extra["progress_callback"] = rp.callback
                    extra["log_callback"] = rp.append_log

                    executor_task = asyncio.get_event_loop().run_in_executor(None, partial(rule.execute, shared_df, **extra))

                    last_heartbeat = time.perf_counter()
                    while not executor_task.done():
                        await asyncio.sleep(0.5)
                        now = time.perf_counter()
                        # Refresh from DB to detect pause/stop requested by user
                        await session.refresh(project)
                        prog_db = dict(project.progress or {})
                        # Stop requested while rule is running
                        if prog_db.get("skip_requested"):
                            logger.info("Stop requested during rule execution %s", rule.name)
                            break
                        # Pause requested while rule is running → wait
                        if project.status == "paused":
                            rules_progress[i]["status"] = "paused"
                            _save_progress(project, rules_progress, total=total, completed=i, current=i + 1, current_rule=rule.name, status="paused")
                            await session.commit()
                            while True:
                                await asyncio.sleep(1)
                                await session.refresh(project)
                                if project.status == "running":
                                    rules_progress[i]["status"] = "running"
                                    break
                                prog_pause = dict(project.progress or {})
                                if prog_pause.get("skip_requested"):
                                    break
                            if project.status != "running":
                                break
                            last_heartbeat = time.perf_counter()
                            continue
                        with rp.lock:
                            needs_update = rp.dirty or (now - last_heartbeat >= 2.0)
                            if needs_update:
                                p = dict(project.progress or {})
                                if p:
                                    elapsed_sec = round(now - t0)
                                    if rp.dirty:
                                        p["rule_processed"] = rp.processed
                                        p["rule_total"] = rp.total
                                        p["rule_phase"] = rp.phase
                                        if rp.extra:
                                            p["rule_extra"] = _safe_val(rp.extra)
                                        else:
                                            p.pop("rule_extra", None)
                                    p["rule_message"] = rp.message or f"Procesando regla: {rule.name} ({elapsed_sec}s)"
                                    # Real-time records estimate
                                    if rp.total > 0:
                                        current_est = int((rp.processed / rp.total) * total_records)
                                    else:
                                        current_est = 0
                                    p["records_processed"] = _safe_val(records_processed + current_est)
                                    if rp.dirty and rp.logs:
                                        logs = p.get("logs", [])
                                        if not isinstance(logs, list):
                                            logs = []
                                        logs.extend(rp.logs)
                                        p["logs"] = logs[-200:]
                                        rp.logs.clear()
                                    project.progress = p
                                    rp.dirty = False
                                    last_heartbeat = now
                                    await session.commit()

                    # Check if we broke out of heartbeat loop due to stop/pause
                    await session.refresh(project)
                    prog_check = dict(project.progress or {})
                    if prog_check.get("skip_requested") or project.status in ("cancelled", "paused"):
                        logger.info("Stop/pause during rule %s, skipping result wait", rule.name)
                        # The executor_thread will finish on its own; we just don't await it
                        if prog_check.get("skip_requested"):
                            rules_progress[i]["status"] = "skipped"
                            _cancel_remaining(i + 1)
                            prog_check.pop("skip_requested", None)
                            project.progress = dict(prog_check)
                            _save_progress(project, rules_progress, total=total, completed=i + 1, current=i + 1, current_rule="", status="cancelled")
                            await session.commit()
                            stopped = True
                            break
                        elif project.status == "paused":
                            # Paused during rule execution — wait here until resume or stop
                            while True:
                                await asyncio.sleep(1)
                                await session.refresh(project)
                                if project.status == "running":
                                    break
                                prog_pause = dict(project.progress or {})
                                if prog_pause.get("skip_requested"):
                                    rules_progress[i]["status"] = "skipped"
                                    _cancel_remaining(i + 1)
                                    project.status = "cancelled"
                                    project.progress = dict(prog_pause)
                                    _save_progress(project, rules_progress, total=total, completed=i + 1, current=i + 1, current_rule="", status="cancelled")
                                    await session.commit()
                                    stopped = True
                                    break
                            if stopped:
                                break
                            last_heartbeat = time.perf_counter()
                            continue

                    result = await executor_task
                    result.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
                    # After execution: skip_requested during rule → cancel all remaining, stop
                    await session.refresh(project)
                    prog = dict(project.progress or {})
                    if prog.pop("skip_requested", False):
                        logger.info("Cancelling analysis (stop requested during rule %d/%s)", i + 1, rule.name)
                        rules_progress[i]["status"] = "skipped"
                        _cancel_remaining(i + 1)
                        project.progress = dict(prog)
                        _save_progress(project, rules_progress, total=total, completed=i + 1, current=i + 1, current_rule=rule.name, status="cancelled")
                        await session.commit()
                        stopped = True
                        break
                    results.append(result)
                    rules_progress[i]["status"] = "done"
                    rules_progress[i]["passed"] = result.passed
                    rules_progress[i]["failed"] = result.failed
                    n = result.total or 0
                    rules_progress[i]["rule_records_processed"] = n
                    records_processed += n
                    _save_progress(project, rules_progress, total=total, completed=i + 1, current=i + 1, current_rule=rule.name, status="running", records_processed=records_processed)
                except Exception as e:
                    logger.exception("Rule %s failed: %s", rule.name, e)
                    elapsed = round((time.perf_counter() - t0) * 1000, 2)
                    # After failure: skip_requested during rule → cancel all remaining, stop
                    await session.refresh(project)
                    prog = dict(project.progress or {})
                    if prog.pop("skip_requested", False):
                        logger.info("Cancelling analysis (stop requested during failed rule %d/%s)", i + 1, rule.name)
                        rules_progress[i]["status"] = "skipped"
                        _cancel_remaining(i + 1)
                        project.progress = dict(prog)
                        _save_progress(project, rules_progress, total=total, completed=i + 1, current=i + 1, current_rule=rule.name, status="cancelled")
                        await session.commit()
                        stopped = True
                        break
                    results.append(RuleResult(
                        rule_name=rule.name, description=rule.description, severity=rule.severity,
                        passed=False, total=0, failed=0, failure_pct=0,
                        details=[{"error": str(e)}], recommendation=f"Error: {e}",
                        duration_ms=elapsed,
                    ))
                    rules_progress[i]["status"] = "failed"
                    rules_progress[i]["error"] = str(e)
                    rules_progress[i]["rule_records_processed"] = 0
                    _save_progress(project, rules_progress, total=total, completed=i + 1, current=i + 1, current_rule=rule.name, status="running")
                await session.commit()

            if duckdb_conn is not None:
                try:
                    duckdb_conn.close()
                except Exception:
                    pass

            if stopped:
                project.status = "cancelled"
                _save_progress(project, rules_progress, total=total, completed=sum(1 for r in rules_progress if r["status"] in ("done", "skipped")), current=total,
                               status="cancelled", records_processed=records_processed)
                await session.commit()
                logger.info("Analysis cancelled by user: project=%s", project_id)
            else:
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
                _save_progress(project, rules_progress, total=total, completed=total,
                               status="completed", score=score, label=label, report_id=str(report.id),
                               records_processed=records_processed)
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
    source_id = req.source_id
    row_limit = None
    storage_mode = "memory"
    selected_columns = None

    if source_id:
        result = await session.execute(
            select(Source).where(Source.id == source_id, Source.user_id == user.id)
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
        row_limit = s.row_limit
        storage_mode = s.storage_mode or "memory"
        selected_columns = s.selected_columns

    load_kwargs = {}
    if row_limit:
        load_kwargs["nrows"] = row_limit
    load_kwargs["storage_mode"] = storage_mode

    source_config = {
        "source_type": st,
        "connection_string": cs,
        "query": q,
        "file_path": fp,
    }
    if req.columns:
        source_config["selected_columns"] = req.columns
    elif selected_columns:
        source_config["selected_columns"] = selected_columns

    project = Project(
        user_id=user.id,
        group_id=req.group_id,
        name=req.project_name or f"Análisis",
        source_config=source_config,
        rules_config=req.rules,
        status="loading",
        progress={
            "total": 0,
            "completed": 0,
            "current": 0,
            "current_rule": "",
            "status": "loading",
            "load_message": "Iniciando carga de datos...",
            "records_loaded": 0,
            "total_records": 0,
            "score": None,
            "label": None,
            "report_id": None,
            "rules": [],
        },
    )
    session.add(project)
    await session.commit()

    asyncio.create_task(load_and_analyze_background(
        project_id=project.id,
        source_type=st,
        connection_string=cs,
        query=q,
        file_path=fp,
        load_kwargs=load_kwargs,
        columns=req.columns,
        selected_columns=selected_columns,
        rules_config=req.rules,
        user_id=user.id,
        rule_configs=req.rule_configs,
    ))

    return {"project_id": str(project.id), "status": "loading"}


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
            await session.refresh(project)
            p = project

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
            if status in ("completed", "failed", "cancelled"):
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
