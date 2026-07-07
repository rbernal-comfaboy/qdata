"""Shared data loading utility for all source types.

Integrates with the DataCube for in-memory caching of loaded datasets.
"""

import pandas as pd


_FILE_TYPES = {"csv", "excel", "json", "parquet"}
_CHUNK_SIZE = 10_000


def _apply_limit(sql: str, limit: int, source_type: str = "") -> str:
    sql = sql.strip().rstrip(";")
    upper = sql.upper()
    if "LIMIT" in upper.split()[-5:]:
        return sql
    if upper.startswith("SELECT"):
        if source_type == "sqlserver":
            return f"SELECT TOP {limit} * FROM ({sql}) AS _limited_"
        return f"SELECT * FROM ({sql}) AS _limited_ LIMIT {limit}"
    return sql


def _check_cube(source_type: str, connection_string: str, query: str, file_path: str, nrows: int | None):
    """Check the DataCube for cached data. Returns DataFrame or None."""
    try:
        from qdata.core.cube import DataCubeManager
        cube_mgr = DataCubeManager.get_instance()
        cache_key = DataCubeManager.make_key(source_type, connection_string or "", query or "", file_path or "")
        cube = cube_mgr.get(cache_key)
        if cube:
            df = cube.get_dataframe()
            if nrows is not None and len(df) > nrows:
                df = df.head(nrows)
            return df
    except Exception:
        pass
    return None


def _store_cube(source_type: str, connection_string: str, query: str, file_path: str, df: pd.DataFrame):
    """Store a DataFrame in the DataCube."""
    try:
        from qdata.core.cube import DataCubeManager
        cube_mgr = DataCubeManager.get_instance()
        cache_key = DataCubeManager.make_key(source_type, connection_string or "", query or "", file_path or "")
        cube_mgr.put(cache_key, df)
    except Exception:
        pass


def load_data(source_type: str, connection_string: str, query: str, file_path: str, **kwargs) -> pd.DataFrame:
    nrows = kwargs.pop("nrows", None)
    storage_mode = kwargs.pop("storage_mode", "memory")
    progress_callback = kwargs.pop("progress_callback", None)

    # Skip cube for connection mode — always query live
    if storage_mode == "memory":
        cached = _check_cube(source_type, connection_string, query, file_path, nrows)
        if cached is not None:
            if progress_callback:
                progress_callback(len(cached), len(cached), "Datos cargados desde caché")
            return cached

    if source_type in _FILE_TYPES:
        kw = {}
        if nrows:
            kw["nrows"] = nrows
        df = _load_file(source_type, file_path, progress_callback=progress_callback, **kw)
    else:
        q = _apply_limit(query, nrows, source_type) if nrows and source_type != "informix" else query

        def _load_with(q: str) -> pd.DataFrame:
            if source_type == "postgresql":
                from qdata.connectors.postgres import PostgresConnector
                c = PostgresConnector(connection_string)
                return c.load(q, progress_callback=progress_callback)
            elif source_type == "mysql":
                from qdata.connectors.mysql import MySQLConnector
                c = MySQLConnector(connection_string)
                return c.load(q, progress_callback=progress_callback)
            elif source_type == "sqlserver":
                from qdata.connectors.sqlserver import SQLServerConnector
                c = SQLServerConnector(connection_string)
                return c.load(q, progress_callback=progress_callback)
            elif source_type == "oracle":
                from qdata.connectors.oracle import OracleConnector
                c = OracleConnector(connection_string)
                return c.load(q, progress_callback=progress_callback)
            elif source_type == "informix":
                from qdata.connectors.informix import InformixConnector
                c = InformixConnector(connection_string)
                return c.load(q, progress_callback=progress_callback, nrows=nrows or 0)
            elif source_type == "sqlite":
                from qdata.connectors.sqlite import SQLiteConnector
                c = SQLiteConnector(file_path)
                return c.load(q, progress_callback=progress_callback)
            else:
                raise ValueError(f"Unsupported source type: {source_type}")

        try:
            df = _load_with(q)
        except Exception:
            if nrows and q != query:
                df = _load_with(query)
            else:
                raise

    # Only cache full data loads (no row limit) in memory mode — partial previews skip the cube
    if nrows is None and not df.empty and storage_mode == "memory":
        if progress_callback:
            progress_callback(len(df), len(df), "Guardando en caché...")
        _store_cube(source_type, connection_string, query, file_path, df)

    # Apply nrows limit to returned data if needed
    if nrows is not None and len(df) > nrows:
        df = df.head(nrows)

    return df


def _load_file(source_type: str, file_path: str, **kwargs) -> pd.DataFrame:
    progress_callback = kwargs.pop("progress_callback", None)
    if source_type == "csv":
        from qdata.connectors.csv_conn import CSVConnector
        c = CSVConnector(file_path)
        return c.load(progress_callback=progress_callback, **kwargs)
    elif source_type == "excel":
        from qdata.connectors.excel_conn import ExcelConnector
        c = ExcelConnector(file_path)
        return c.load(**kwargs)
    elif source_type == "json":
        from qdata.connectors.json_conn import JSONConnector
        c = JSONConnector(file_path)
        return c.load(**kwargs)
    elif source_type == "parquet":
        from qdata.connectors.parquet_conn import ParquetConnector
        c = ParquetConnector(file_path)
        return c.load(**kwargs)
    else:
        raise ValueError(f"Unsupported file type: {source_type}")
