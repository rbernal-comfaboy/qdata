import asyncio
import json
import os
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from qdata.auth.dependencies import get_current_user
from qdata.core.loader import load_data
from qdata.db.models import DataSource, Source, User
from qdata.db.session import get_session

# Initialize Oracle thick mode if Instant Client is available
_instantclient_path = "/opt/oracle/instantclient"
if os.path.isdir(_instantclient_path):
    import oracledb
    oracledb.init_oracle_client(lib_dir=_instantclient_path)

router = APIRouter()

DEFAULT_PORTS = {
    "postgresql": 5432,
    "mysql": 3306,
    "sqlserver": 1433,
    "oracle": 1521,
    "informix": 9088,
}


def _detect_sqlserver_driver() -> str:
    """Return the best available ODBC driver name for SQL Server."""
    candidates = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
    ]
    try:
        import pyodbc
        available = {d.lower() for d in pyodbc.drivers()}
        for c in candidates:
            if c.lower() in available:
                return c.replace(" ", "+")
    except ImportError:
        pass
    return "SQL+Server"


def build_connection_string(source_type: str, fields: dict) -> str:
    host = fields.get("host", "")
    port = fields.get("port")
    database = fields.get("database", "")
    username = fields.get("username", "")
    password = fields.get("password", "")
    ssl = fields.get("ssl", False)

    if source_type == "postgresql":
        port = port or DEFAULT_PORTS["postgresql"]
        pw = _url_encode(password)
        cs = f"postgresql://{username}:{pw}@{host}:{port}/{database}"
        if ssl:
            cs += "?sslmode=require"
        return cs
    elif source_type == "mysql":
        port = port or DEFAULT_PORTS["mysql"]
        pw = _url_encode(password)
        return f"mysql+pymysql://{username}:{pw}@{host}:{port}/{database}"
    elif source_type == "sqlserver":
        instance = fields.get("instance", "")
        port = port or DEFAULT_PORTS["sqlserver"]
        pw = _url_encode(password)
        driver = _detect_sqlserver_driver()
        if instance:
            cs = f"mssql+pyodbc://{username}:{pw}@{host}\\{instance}/{database}?driver={driver}"
        else:
            cs = f"mssql+pyodbc://{username}:{pw}@{host}:{port}/{database}?driver={driver}"
        if not ssl:
            cs += "&TrustServerCertificate=yes"
        return cs
    elif source_type == "oracle":
        port = port or DEFAULT_PORTS["oracle"]
        pw = _url_encode(password)
        return f"oracle+oracledb://{username}:{pw}@{host}:{port}/{database}"
    elif source_type == "informix":
        port = port or DEFAULT_PORTS["informix"]
        return f"informix+pyodbc://{username}:{password}@{host}:{port}/{database}"
    elif source_type == "sqlite":
        return f"sqlite:///{database}"
    return ""


def _url_encode(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.\-~]", lambda m: f"%{ord(m.group(0)):02X}", s)


def extract_db_fields(source_type: str, config: dict | None, connection_string: str | None) -> dict:
    if config and isinstance(config, dict) and config.get("db_fields"):
        return config["db_fields"]
    if not connection_string:
        return {"host": "", "port": None, "database": "", "username": "", "password": "", "ssl": False}
    if source_type == "sqlite":
        return {"host": "", "port": None, "database": connection_string.replace("sqlite:///", ""), "username": "", "password": "", "ssl": False}
    m = re.match(r"\w+(?:\+\w+)?://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)(?:\?sslmode=require)?", connection_string)
    if m:
        return {
            "host": m.group(3), "port": int(m.group(4)), "database": m.group(5),
            "username": m.group(1), "password": m.group(2), "ssl": "sslmode=require" in connection_string,
        }
    return {"host": "", "port": None, "database": "", "username": "", "password": "", "ssl": False}


class DBFields(BaseModel):
    host: str = ""
    port: int | None = None
    database: str = ""
    username: str = ""
    password: str = ""
    ssl: bool = False
    instance: str = ""


class DataSourceCreate(BaseModel):
    name: str
    source_type: str
    db_fields: DBFields = DBFields()
    file_path: str = ""
    config: dict = {}


class DataSourceUpdate(BaseModel):
    name: str | None = None
    source_type: str | None = None
    db_fields: DBFields | None = None
    file_path: str | None = None
    config: dict | None = None


class TestConnectionRequest(BaseModel):
    source_type: str
    db_fields: DBFields = DBFields()
    file_path: str = ""


class TestConnectionResponse(BaseModel):
    success: bool
    tables: list[str] = []
    error: str = ""


def _serialize(ds: DataSource) -> dict:
    return {
        "id": str(ds.id),
        "name": ds.name,
        "source_type": ds.source_type,
        "connection_string": ds.connection_string or "",
        "file_path": ds.file_path or "",
        "config": ds.config or {},
        "db_fields": extract_db_fields(ds.source_type, ds.config, ds.connection_string),
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
    }


@router.get("/")
@router.get("")
async def list_datasources(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import desc
    result = await session.execute(
        select(DataSource).where(DataSource.user_id == user.id).order_by(desc(DataSource.created_at))
    )
    return [_serialize(ds) for ds in result.scalars().all()]


@router.get("/{ds_id}")
async def get_datasource(
    ds_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DataSource).where(DataSource.id == ds_id, DataSource.user_id == user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    return _serialize(ds)


@router.post("/", status_code=201)
@router.post("", status_code=201)
async def create_datasource(
    req: DataSourceCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    config = req.config or {}
    if req.db_fields.host:
        config["db_fields"] = req.db_fields.model_dump()
    connection_string = build_connection_string(req.source_type, config.get("db_fields", {})) if config.get("db_fields") else ""

    ds = DataSource(
        user_id=user.id,
        name=req.name,
        source_type=req.source_type,
        connection_string=connection_string,
        file_path=req.file_path,
        config=config,
    )
    session.add(ds)
    await session.commit()
    await session.refresh(ds)
    return _serialize(ds)


@router.put("/{ds_id}")
async def update_datasource(
    ds_id: str,
    req: DataSourceUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DataSource).where(DataSource.id == ds_id, DataSource.user_id == user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    if req.name is not None:
        ds.name = req.name
    if req.source_type is not None:
        ds.source_type = req.source_type
    if req.file_path is not None:
        ds.file_path = req.file_path
    if req.config is not None:
        ds.config = req.config
    if req.db_fields is not None:
        config = ds.config or {}
        config["db_fields"] = req.db_fields.model_dump()
        ds.config = config
        ds.connection_string = build_connection_string(ds.source_type, config["db_fields"])

    await session.commit()
    return {"ok": True}


@router.delete("/{ds_id}")
async def delete_datasource(
    ds_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DataSource).where(DataSource.id == ds_id, DataSource.user_id == user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    # Evict all associated cubes from DuckDB + clean up scheduler jobs
    try:
        sources_result = await session.execute(
            select(Source).where(Source.data_source_id == ds_id)
        )
        sources = sources_result.scalars().all()
        if sources:
            from qdata.core.cube import DataCubeManager
            from qdata.scheduler.service import remove_source_refresh_job
            for s in sources:
                cache_key = DataCubeManager.make_key(
                    source_type=ds.source_type,
                    connection_string=ds.connection_string or "",
                    query=s.query or "",
                    file_path=ds.file_path or "",
                )
                DataCubeManager.get_instance().evict(cache_key)
                if s.refresh_cron:
                    asyncio.create_task(remove_source_refresh_job(str(s.id)))
    except Exception:
        pass
    await session.delete(ds)
    await session.commit()
    return {"ok": True}


@router.post("/test", response_model=TestConnectionResponse)
async def test_connection(req: TestConnectionRequest):
    try:
        if req.source_type in ("csv", "excel", "json", "parquet", "txt"):
            import os
            if not req.file_path or not os.path.isfile(req.file_path):
                return TestConnectionResponse(success=False, error="Archivo no encontrado")
            if req.source_type == "csv":
                import pandas as pd
                pd.read_csv(req.file_path, nrows=5)
            elif req.source_type == "excel":
                import pandas as pd
                pd.read_excel(req.file_path, nrows=5)
            elif req.source_type == "json":
                import pandas as pd
                pd.read_json(req.file_path)
            elif req.source_type == "parquet":
                import pandas as pd
                pd.read_parquet(req.file_path)
            return TestConnectionResponse(success=True, tables=[])

        fields = req.db_fields.model_dump()
        conn_str = build_connection_string(req.source_type, fields)
        if not conn_str:
            return TestConnectionResponse(success=False, error=f"Tipo de fuente no soportado: {req.source_type}")

        tables = []
        if req.source_type == "informix":
            from qdata.connectors.informix import InformixConnector, _get_table_names
            import pyodbc
            conn = pyodbc.connect(conn_str, autocommit=True)
            try:
                conn.execute(text("SELECT 1 FROM systables WHERE tabid = 1"))
                cursor = conn.cursor()
                tables = _get_table_names(cursor)
            finally:
                conn.close()
        else:
            engine = create_engine(conn_str)
            with engine.connect() as conn:
                test_sql = "SELECT 1 FROM DUAL" if req.source_type == "oracle" else "SELECT 1"
                conn.execute(text(test_sql))
            inspector = inspect(engine)
            tables = inspector.get_table_names()
        return TestConnectionResponse(success=True, tables=tables)
    except Exception as e:
        return TestConnectionResponse(success=False, error=str(e)[:300])


def _get_engine(ds: DataSource):
    if ds.source_type in ("csv", "excel", "json", "parquet", "txt"):
        return None
    if ds.source_type == "informix":
        return None
    if ds.source_type == "sqlite":
        cs = ds.connection_string or f"sqlite:///{ds.file_path}"
    else:
        cs = ds.connection_string or ""
    return create_engine(cs) if cs else None


@router.get("/{ds_id}/tables")
async def list_tables(
    ds_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DataSource).where(DataSource.id == ds_id, DataSource.user_id == user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    engine = _get_engine(ds)
    if ds.source_type == "informix":
        import pyodbc
        from qdata.connectors.informix import InformixConnector, _get_table_names
        conn = pyodbc.connect(ds.connection_string or "", autocommit=True)
        try:
            cursor = conn.cursor()
            tables = _get_table_names(cursor)
            cols = []
            for t in tables:
                cursor.execute(
                    "SELECT c.colname, c.coltype, c.nulls "
                    "FROM syscolumns c JOIN systables t ON c.tabid = t.tabid "
                    "WHERE t.tabname = ? AND t.tabid >= 100",
                    t,
                )
                for row in cursor.fetchall():
                    cols.append({"table": t, "column": row[0], "type": str(row[1]), "nullable": row[2] == 1})
            table_list = [{"name": t, "row_count": None} for t in tables]
            return {"tables": table_list, "columns": cols}
        finally:
            conn.close()
    if not engine:
        return {"tables": [], "columns": []}
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        row_counts = _get_row_counts(engine, ds.source_type, tables)
        cols = []
        for t in tables:
            for c in inspector.get_columns(t):
                cols.append({"table": t, "column": c["name"], "type": str(c["type"]), "nullable": c.get("nullable", True)})
        table_list = [{"name": t, "row_count": row_counts.get(t)} for t in tables]
        return {"tables": table_list, "columns": cols}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _get_row_counts(engine, source_type: str, tables: list[str]) -> dict[str, int | None]:
    if not tables:
        return {}
    try:
        with engine.connect() as conn:
            if source_type == "postgresql":
                result = conn.execute(text(
                    "SELECT relname, reltuples::bigint FROM pg_class WHERE relname IN :tbls"
                ), {"tbls": tuple(tables)})
                return {r[0]: r[1] for r in result}
            elif source_type == "mysql":
                result = conn.execute(text(
                    "SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.tables "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN :tbls"
                ), {"tbls": tuple(tables)})
                return {r[0]: r[1] for r in result}
            elif source_type == "sqlserver":
                placeholders = ", ".join(f"'{t}'" for t in tables)
                result = conn.execute(text(
                    f"SELECT OBJECT_NAME(object_id), SUM(rows) FROM sys.partitions "
                    f"WHERE object_id IN (SELECT object_id FROM sys.objects WHERE name IN ({placeholders}) AND type='U') "
                    f"AND index_id IN (0,1) GROUP BY object_id"
                ))
                return {r[0]: r[1] for r in result}
            elif source_type == "oracle":
                placeholders = ", ".join(f"'{t.upper()}'" for t in tables)
                try:
                    result = conn.execute(text(
                        f"SELECT TABLE_NAME, NUM_ROWS FROM ALL_TABLES WHERE TABLE_NAME IN ({placeholders})"
                    ))
                    counts = {r[0]: r[1] for r in result}
                    for t in tables:
                        if t.upper() not in counts:
                            r = conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
                            counts[t.upper()] = r.scalar()
                    return counts
                except Exception:
                    return {t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in tables}
            elif source_type == "sqlite":
                return {t: conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in tables}
    except Exception:
        pass
    return {}


@router.get("/{ds_id}/tables/{table_name}/columns")
async def list_columns(
    ds_id: str,
    table_name: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DataSource).where(DataSource.id == ds_id, DataSource.user_id == user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    engine = _get_engine(ds)
    if not engine:
        return {"columns": []}
    try:
        inspector = inspect(engine)
        cols = []
        for c in inspector.get_columns(table_name):
            cols.append({"name": c["name"], "type": str(c["type"]), "nullable": c.get("nullable", True)})
        return {"columns": cols}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{ds_id}/suggest")
async def suggest_tables(
    ds_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DataSource).where(DataSource.id == ds_id, DataSource.user_id == user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    engine = _get_engine(ds)
    if not engine:
        return {"suggestions": []}

    try:
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        suggestions = []
        for t in all_tables[:200]:
            try:
                cols = inspector.get_columns(t)
            except Exception:
                continue
            col_names = [c["name"] for c in cols]
            row_count = None
            try:
                with engine.connect() as conn:
                    r = conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
                    row_count = r.scalar()
            except Exception:
                pass
            priority = 0
            tags = []
            score = 0
            if row_count and row_count >= 100:
                priority += 1; score += 1
            if row_count and row_count >= 1000:
                priority += 1; score += 1
            if row_count and row_count > 10000:
                priority += 1; score += 1
            name_lower = t.lower()
            if any(k in name_lower for k in ["cliente", "paciente", "persona", "empleado", "user"]):
                tags.append("personas"); score += 2
            if any(k in name_lower for k in ["venta", "factur", "orden", "pedido", "transaccion"]):
                tags.append("transacciones"); score += 2
            if any(k in name_lower for k in ["producto", "inventario", "catalogo", "item"]):
                tags.append("catalogos"); score += 1
            if any(k in name_lower for k in ["nomina", "salario", "pago", "cheque"]):
                tags.append("financiero"); score += 1
            if any(cn.lower() in ("email", "correo") for cn in col_names):
                tags.append("email"); score += 1
            if any(cn.lower() in ("telefono", "phone", "celular") for cn in col_names):
                tags.append("telefono"); score += 1
            if any("fecha" in cn.lower() or "date" in cn.lower() for cn in col_names):
                tags.append("fechas"); score += 0.5
            if any("nombre" in cn.lower() or "name" in cn.lower() for cn in col_names):
                tags.append("nombres"); score += 0.5
            if any("id" == cn.lower().strip() or cn.lower().endswith("_id") for cn in col_names):
                tags.append("id"); score += 0.5
            suggestions.append({
                "table": t,
                "row_count": row_count,
                "columns": len(col_names),
                "col_names": col_names[:20],
                "tags": tags,
                "score": score,
                "reason": _suggest_reason(tags, row_count, score),
            })

        suggestions.sort(key=lambda s: s["score"], reverse=True)
        return {"suggestions": suggestions[:30]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class PreviewQueryRequest(BaseModel):
    query: str = ""
    selected_columns: list[str] = []
    row_limit: int | None = None


@router.post("/{ds_id}/preview-query")
async def preview_datasource_query(
    ds_id: str,
    req: PreviewQueryRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DataSource).where(DataSource.id == ds_id, DataSource.user_id == user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    limit = req.row_limit or 100
    try:
        kwargs = {"nrows": limit + 1} if ds.source_type in ("csv", "excel", "json", "parquet") else {}
        df = load_data(ds.source_type, ds.connection_string or "", req.query, ds.file_path or "", **kwargs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error loading data: {e}")

    if df.empty:
        return {"columns": [], "rows": [], "total_rows": 0}

    if req.selected_columns:
        sel = [c for c in req.selected_columns if c in df.columns]
        if sel:
            df = df[sel]

    total = len(df)
    head = df.head(min(20, total))
    return {
        "columns": [str(c) for c in df.columns],
        "rows": json.loads(head.to_json(orient="values")),
        "total_rows": total,
    }


def _suggest_reason(tags: list, row_count: int | None, score: int) -> str:
    reasons = []
    if "personas" in tags:
        reasons.append("contiene datos personales")
    if "transacciones" in tags:
        reasons.append("alta cardinalidad de transacciones")
    if "catalogos" in tags:
        reasons.append("posibles duplicados en catálogo")
    if "financiero" in tags:
        reasons.append("datos financieros sensibles")
    if "email" in tags:
        reasons.append("validación de emails")
    if "telefono" in tags:
        reasons.append("validación de teléfonos")
    if "fechas" in tags:
        reasons.append("series temporales")
    if "nombres" in tags:
        reasons.append("posibles duplicados por nombre")
    if "id" in tags:
        reasons.append("integridad referencial")
    if row_count and row_count > 1000:
        reasons.append(f"{row_count} registros")
    return ", ".join(reasons[:3]) if reasons else ("muchos registros" if row_count and row_count > 100 else "volumen moderado")
