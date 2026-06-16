"""Shared data loading utility for all source types.

Integrates with the DataCube for in-memory caching of loaded datasets.
"""

import pandas as pd


_FILE_TYPES = {"csv", "excel", "json", "parquet"}


def _apply_limit(sql: str, limit: int) -> str:
    sql = sql.strip().rstrip(";")
    upper = sql.upper()
    if "LIMIT" in upper.split()[-5:]:
        return sql
    if upper.startswith("SELECT"):
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
    except ImportError:
        pass
    return None


def _store_cube(source_type: str, connection_string: str, query: str, file_path: str, df: pd.DataFrame):
    """Store a DataFrame in the DataCube."""
    try:
        from qdata.core.cube import DataCubeManager
        cube_mgr = DataCubeManager.get_instance()
        cache_key = DataCubeManager.make_key(source_type, connection_string or "", query or "", file_path or "")
        cube_mgr.put(cache_key, df)
    except ImportError:
        pass


def load_data(source_type: str, connection_string: str, query: str, file_path: str, **kwargs) -> pd.DataFrame:
    nrows = kwargs.pop("nrows", None)
    storage_mode = kwargs.pop("storage_mode", "memory")

    # Skip cube for connection mode — always query live
    if storage_mode == "memory":
        cached = _check_cube(source_type, connection_string, query, file_path, nrows)
        if cached is not None:
            return cached

    if source_type in _FILE_TYPES:
        kw = {}
        if nrows:
            kw["nrows"] = nrows
        df = _load_file(source_type, file_path, **kw)
    else:
        q = _apply_limit(query, nrows) if nrows else query

        if source_type == "postgresql":
            from qdata.connectors.postgres import PostgresConnector
            c = PostgresConnector(connection_string)
            df = c.load(q)
        elif source_type == "mysql":
            from qdata.connectors.mysql import MySQLConnector
            c = MySQLConnector(connection_string)
            df = c.load(q)
        elif source_type == "sqlserver":
            from qdata.connectors.sqlserver import SQLServerConnector
            c = SQLServerConnector(connection_string)
            df = c.load(q)
        elif source_type == "sqlite":
            from qdata.connectors.sqlite import SQLiteConnector
            c = SQLiteConnector(file_path)
            df = c.load(q)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

    # Only cache full data loads (no row limit) in memory mode — partial previews skip the cube
    if nrows is None and not df.empty and storage_mode == "memory":
        _store_cube(source_type, connection_string, query, file_path, df)

    # Apply nrows limit to returned data if needed
    if nrows is not None and len(df) > nrows:
        df = df.head(nrows)

    return df


def _load_file(source_type: str, file_path: str, **kwargs) -> pd.DataFrame:
    if source_type == "csv":
        from qdata.connectors.csv_conn import CSVConnector
        c = CSVConnector(file_path)
    elif source_type == "excel":
        from qdata.connectors.excel_conn import ExcelConnector
        c = ExcelConnector(file_path)
    elif source_type == "json":
        from qdata.connectors.json_conn import JSONConnector
        c = JSONConnector(file_path)
    elif source_type == "parquet":
        from qdata.connectors.parquet_conn import ParquetConnector
        c = ParquetConnector(file_path)
    else:
        raise ValueError(f"Unsupported file type: {source_type}")
    return c.load(**kwargs)
