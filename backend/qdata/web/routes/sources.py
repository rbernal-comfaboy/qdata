import asyncio
import math
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from qdata.auth.dependencies import get_current_user
from qdata.core.loader import load_data
from qdata.db.models import Source, DataSource, User
from qdata.db.session import get_session
from qdata.scheduler.service import add_source_refresh_job, refresh_source_cube, remove_source_refresh_job

router = APIRouter()


def _safe_val(v: Any) -> Any:
    if isinstance(v, (float, int)):
        if math.isinf(v) or math.isnan(v):
            return str(v)
        return v
    if isinstance(v, dict):
        return {k: _safe_val(v) for k, v in v.items()}
    if isinstance(v, (list, tuple)):
        return [_safe_val(x) for x in v]
    if hasattr(v, "item"):
        return _safe_val(v.item())
    if v is None:
        return None
    try:
        json.dumps(v)
        return v
    except (TypeError, ValueError):
        return str(v)


class SourceCreate(BaseModel):
    name: str
    data_source_id: str
    query: str = ""
    selected_columns: list[str] = []
    row_limit: int | None = None
    storage_mode: str = "connection"
    refresh_cron: str | None = None


class SourceUpdate(BaseModel):
    name: str | None = None
    data_source_id: str | None = None
    query: str | None = None
    selected_columns: list[str] | None = None
    row_limit: int | None = None
    storage_mode: str | None = None
    refresh_cron: str | None = None


@router.get("/")
async def list_sources(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Source).where(Source.user_id == user.id).order_by(desc(Source.created_at))
    )
    sources = result.scalars().all()
    out = []
    for s in sources:
        ds = await session.get(DataSource, s.data_source_id)
        pd = s.preview_data or {}
        total_rows = pd.get("total_rows") if isinstance(pd, dict) else None
        if total_rows is None and ds:
            is_file = ds.source_type in ("csv", "excel", "json", "parquet", "txt")
            q = s.query or ""
            try:
                if q.strip() and not is_file:
                    import re
                    count_sql = re.sub(r"SELECT\s+.+?\s+FROM", "SELECT COUNT(*) FROM", q, count=1, flags=re.I)
                    if count_sql != q:
                        df = load_data(ds.source_type, ds.connection_string or "", count_sql, "")
                        total_rows = df.iloc[0, 0] if not df.empty else None
                if total_rows is None and is_file:
                    df = load_data(ds.source_type, ds.connection_string or "", "", ds.file_path or "")
                    total_rows = len(df)
            except Exception:
                pass
        out.append({
            "id": str(s.id),
            "name": s.name,
            "data_source_id": str(s.data_source_id),
            "data_source_name": ds.name if ds else "Eliminada",
            "source_type": ds.source_type if ds else "unknown",
            "query": s.query or "",
            "selected_columns": s.selected_columns or [],
            "row_limit": s.row_limit,
            "storage_mode": s.storage_mode or "connection",
            "refresh_cron": s.refresh_cron,
            "refresh_enabled": s.refresh_enabled,
            "total_rows": total_rows,
            "columns_count": len(s.selected_columns) if s.selected_columns else None,
            "preview_data": pd,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return out


async def _preload_source(source_id: str, data_source_id: str, query: str, file_path: str):
    """Background preload of source data into DuckDB cube."""
    import logging
    logger = logging.getLogger("qdata.sources.preload")
    try:
        from qdata.core.loader import load_data as _ld
        from qdata.db.session import async_session_factory
        from qdata.db.models import DataSource as _DS
        async with async_session_factory() as ses:
            ds = await ses.get(_DS, data_source_id)
            if ds:
                _ld(ds.source_type, ds.connection_string or "", query or "", file_path or "", storage_mode="memory")
                logger.info("Preload complete for source %s", source_id)
    except Exception as e:
        logger.warning("Preload failed for source %s: %s", source_id, e)


@router.post("/", status_code=201)
async def create_source(
    req: SourceCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ds = await session.get(DataSource, req.data_source_id)
    if not ds or ds.user_id != user.id:
        raise HTTPException(status_code=404, detail="Data source not found")

    s = Source(
        user_id=user.id,
        data_source_id=req.data_source_id,
        name=req.name,
        query=req.query,
        selected_columns=req.selected_columns,
        row_limit=req.row_limit,
        storage_mode=req.storage_mode or "connection",
        refresh_cron=req.refresh_cron if req.storage_mode == "memory" else None,
        refresh_enabled=bool(req.refresh_cron and req.storage_mode == "memory"),
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)

    # Background preload for memory mode — response returns immediately
    if s.storage_mode == "memory":
        asyncio.create_task(_preload_source(
            source_id=str(s.id),
            data_source_id=str(s.data_source_id),
            query=s.query or "",
            file_path=ds.file_path or "",
        ))
        if s.refresh_cron:
            asyncio.create_task(add_source_refresh_job(str(s.id), s.refresh_cron))

    return {"id": str(s.id), "name": s.name}


@router.get("/{source_id}")
async def get_source(
    source_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user.id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Source not found")

    ds = await session.get(DataSource, s.data_source_id)
    pd = s.preview_data or {}
    return {
        "id": str(s.id),
        "name": s.name,
        "data_source_id": str(s.data_source_id),
        "data_source_name": ds.name if ds else "Eliminada",
        "source_type": ds.source_type if ds else "unknown",
        "connection_string": ds.connection_string if ds else "",
        "file_path": ds.file_path if ds else "",
        "query": s.query or "",
        "selected_columns": s.selected_columns or [],
        "row_limit": s.row_limit,
        "storage_mode": s.storage_mode or "connection",
        "refresh_cron": s.refresh_cron,
        "refresh_enabled": s.refresh_enabled,
        "total_rows": pd.get("total_rows") if isinstance(pd, dict) else None,
        "columns_count": len(s.selected_columns) if s.selected_columns else None,
        "preview_data": pd,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.put("/{source_id}")
async def update_source(
    source_id: str,
    req: SourceUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user.id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Source not found")
    if req.name is not None:
        s.name = req.name
    if req.data_source_id is not None:
        s.data_source_id = req.data_source_id
    if req.query is not None:
        s.query = req.query
    if req.storage_mode is not None:
        s.storage_mode = req.storage_mode
    if req.selected_columns is not None:
        s.selected_columns = req.selected_columns
    if req.row_limit is not None:
        s.row_limit = req.row_limit

    # Handle refresh cron changes
    if req.refresh_cron is not None:
        old_cron = s.refresh_cron
        s.refresh_cron = req.refresh_cron
        s.refresh_enabled = bool(req.refresh_cron and s.storage_mode == "memory")
        if s.storage_mode == "memory":
            if s.refresh_cron:
                asyncio.create_task(add_source_refresh_job(str(s.id), s.refresh_cron))
            elif old_cron:
                asyncio.create_task(remove_source_refresh_job(str(s.id)))
    elif s.refresh_cron and s.storage_mode == "connection":
        # Disabling memory mode — remove refresh job
        asyncio.create_task(remove_source_refresh_job(str(s.id)))
        s.refresh_cron = None
        s.refresh_enabled = False

    await session.commit()
    return {"ok": True}


@router.delete("/{source_id}")
async def delete_source(
    source_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user.id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Source not found")
    if s.refresh_cron:
        asyncio.create_task(remove_source_refresh_job(str(s.id)))
    # Evict from DuckDB cube cache
    try:
        ds = await session.get(DataSource, s.data_source_id)
        if ds:
            from qdata.core.cube import DataCubeManager
            cache_key = DataCubeManager.make_key(
                source_type=ds.source_type,
                connection_string=ds.connection_string or "",
                query=s.query or "",
                file_path=ds.file_path or "",
            )
            DataCubeManager.get_instance().evict(cache_key)
    except Exception:
        pass
    await session.delete(s)
    await session.commit()
    return {"ok": True}


@router.post("/{source_id}/refresh")
async def refresh_source(
    source_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user.id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Source not found")
    if s.storage_mode != "memory":
        raise HTTPException(status_code=400, detail="Source is not in memory mode")
    asyncio.create_task(refresh_source_cube(str(s.id)))
    return {"status": "refreshing"}


class PreviewResponse(BaseModel):
    columns: list[str]
    rows: list[list]
    total_rows: int


@router.post("/{source_id}/preview", response_model=PreviewResponse)
async def preview_source(
    source_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user.id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Source not found")

    ds = await session.get(DataSource, s.data_source_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    try:
        kwargs = {"nrows": 11}
        kwargs["storage_mode"] = s.storage_mode or "memory"
        df = load_data(ds.source_type, ds.connection_string or "", s.query or "", ds.file_path or "", **kwargs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error loading data: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="No data returned")

    if s.selected_columns:
        df = df[[c for c in s.selected_columns if c in df.columns]]

    if s.row_limit and len(df) > s.row_limit:
        df = df.head(s.row_limit)

    total = len(df)
    head = df.head(min(20, total))
    preview = {
        "columns": [str(c) for c in df.columns],
        "rows": json.loads(head.to_json(orient="values")),
        "total_rows": total,
    }
    s.preview_data = preview
    await session.commit()

    return PreviewResponse(**preview)


async def _preview_data(s: Source) -> dict | None:
    from qdata.db.session import session_factory
    async with session_factory() as session:
        ds = await session.get(DataSource, s.data_source_id)
        if not ds:
            return None
        try:
            kwargs = {"nrows": 11}
            kwargs["storage_mode"] = s.storage_mode or "memory"
            df = load_data(ds.source_type, ds.connection_string or "", s.query or "", ds.file_path or "", **kwargs)
            if df.empty:
                return None
            if s.selected_columns:
                df = df[[c for c in s.selected_columns if c in df.columns]]
            head = df.head(10)
            preview = {
                "columns": [str(c) for c in df.columns],
                "rows": json.loads(head.to_json(orient="values")),
                "total_rows": len(df),
            }
            s.preview_data = preview
            await session.commit()
            return preview
        except Exception:
            return None
