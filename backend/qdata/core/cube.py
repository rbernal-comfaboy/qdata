"""In-memory Data Cube using DuckDB for zero-copy columnar analytics."""

import hashlib
import json
import logging
import threading
import time
from typing import Any, Callable, Optional

import pandas as pd

logger = logging.getLogger("qdata.cube")


class DataCube:
    """An in-memory data cube backed by DuckDB.

    Stores a DataFrame as a DuckDB table (zero-copy when registered from pandas)
    and pre-computes column statistics for fast profiling.
    """

    def __init__(self, key: str, df: pd.DataFrame, conn: Any):
        self.key = key
        self.conn = conn
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.size_bytes = int(df.memory_usage(deep=True).sum())
        self.row_count = len(df)
        self.column_count = len(df.columns)

        conn.register("data", df)
        self._build_profile(df)

    def _build_profile(self, df: pd.DataFrame):
        profile = {}
        for col in df.columns:
            col_data = df[col]
            entry: dict[str, Any] = {
                "dtype": str(col_data.dtype),
                "nulls": int(col_data.isna().sum()),
                "non_null": int(col_data.notna().sum()),
                "null_pct": round(float(col_data.isna().mean() * 100), 2),
                "distinct": int(col_data.nunique()),
            }
            if col_data.dtype in ("int64", "float64", "int32", "float32", "Int64", "Float64"):
                non_null = col_data.dropna()
                if len(non_null) > 0:
                    entry["min"] = float(non_null.min())
                    entry["max"] = float(non_null.max())
                    entry["mean"] = float(non_null.mean())
                    entry["std"] = float(non_null.std())
            elif col_data.dtype == "object":
                str_data = col_data.dropna().astype(str)
                if len(str_data) > 0:
                    lengths = str_data.str.len()
                    entry["min_length"] = int(lengths.min())
                    entry["max_length"] = int(lengths.max())
            profile[col] = entry
        self.profile = profile

    def query(self, sql: str) -> pd.DataFrame:
        self.last_accessed = time.time()
        return self.conn.execute(sql).fetchdf()

    def query_arrow(self, sql: str) -> Any:
        self.last_accessed = time.time()
        return self.conn.execute(sql).fetch_arrow_table()

    def get_dataframe(self) -> pd.DataFrame:
        return self.query("SELECT * FROM data")

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


class DataCubeManager:
    _instance: Optional["DataCubeManager"] = None
    _lock = threading.Lock()

    def __init__(self, max_memory_mb: int = 2048, default_ttl: int = 1800):
        self.cubes: dict[str, DataCube] = {}
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.default_ttl = default_ttl

    @classmethod
    def get_instance(cls, **kwargs) -> "DataCubeManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance

    @staticmethod
    def make_key(
        source_type: str,
        connection_string: str = "",
        query: str = "",
        file_path: str = "",
        selected_columns: list[str] | None = None,
    ) -> str:
        raw = json.dumps(
            {
                "st": source_type,
                "cs": connection_string,
                "q": query,
                "fp": file_path,
                "sc": selected_columns,
            },
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, key: str) -> Optional[DataCube]:
        cube = self.cubes.get(key)
        if cube is None:
            return None
        if time.time() - cube.created_at > self.default_ttl:
            logger.info("Evicting expired cube %s (TTL)", key[:8])
            self.evict(key)
            return None
        cube.last_accessed = time.time()
        return cube

    def put(self, key: str, df: pd.DataFrame) -> DataCube:
        self._ensure_space(df.memory_usage(deep=True).sum())
        try:
            import duckdb
            conn = duckdb.connect(":memory:")
            cube = DataCube(key, df, conn)
            self.cubes[key] = cube
            logger.info(
                "Cached cube %s: %d rows, %d cols, %.1f MB",
                key[:8],
                cube.row_count,
                cube.column_count,
                cube.size_bytes / (1024 * 1024),
            )
            return cube
        except ImportError:
            logger.warning("duckdb not available, skipping cube cache")
            raise

    def get_or_load(self, key: str, loader: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        cube = self.get(key)
        if cube is not None:
            logger.debug("Cube hit for %s", key[:8])
            return cube.get_dataframe()
        logger.debug("Cube miss for %s, loading...", key[:8])
        df = loader()
        if df is not None and not df.empty:
            try:
                self.put(key, df)
            except ImportError:
                pass
        return df

    def _ensure_space(self, needed_bytes: int):
        while True:
            total = sum(c.size_bytes for c in self.cubes.values())
            if total + needed_bytes <= self.max_memory_bytes:
                break
            if not self.cubes:
                break
            oldest = min(self.cubes.values(), key=lambda c: c.last_accessed)
            logger.info("Evicting cube %s to free %.1f MB", oldest.key[:8], oldest.size_bytes / (1024 * 1024))
            self.evict(oldest.key)

    def evict(self, key: str):
        cube = self.cubes.pop(key, None)
        if cube:
            cube.close()

    def clear(self):
        for key in list(self.cubes.keys()):
            self.evict(key)

    def get_stats(self) -> dict:
        return {
            "cubes": len(self.cubes),
            "total_rows": sum(c.row_count for c in self.cubes.values()),
            "total_memory_mb": round(sum(c.size_bytes for c in self.cubes.values()) / (1024 * 1024), 2),
            "max_memory_mb": round(self.max_memory_bytes / (1024 * 1024)),
        }
