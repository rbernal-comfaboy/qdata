import pyodbc
import pandas as pd

from qdata.connectors.base import Connector


_INFORMIX_DRIVERS = [
    "IBM INFORMIX ODBC DRIVER (64-bit)",
    "IBM INFORMIX ODBC DRIVER",
    "Informix",
    "INFORMIX",
]


def _detect_driver() -> str | None:
    try:
        available = {d.lower() for d in pyodbc.drivers()}
        for d in _INFORMIX_DRIVERS:
            if d.lower() in available:
                return d
    except Exception:
        pass
    return None


def build_odbc_conn_str(host: str, port: int, database: str, username: str, password: str, server: str = "") -> str:
    driver = _detect_driver() or "Informix"
    svr = server or host
    return (
        f"DRIVER={{{driver}}};"
        f"HOST={host};SERVICE={port};SERVER={svr};"
        f"DATABASE={database};UID={username};PWD={password};"
        f"PROTOCOL=onsoctcp"
    )


def _get_table_names(cursor) -> list[str]:
    cursor.execute("SELECT tabname FROM systables WHERE tabid >= 100 AND tabtype = 'T' ORDER BY tabname")
    return [r[0] for r in cursor.fetchall()]


class InformixConnector(Connector):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    def _connect(self):
        return pyodbc.connect(self.connection_string, autocommit=True)

    def load(self, query: str, progress_callback=None) -> pd.DataFrame:
        conn = self._connect()
        try:
            if not progress_callback:
                return pd.read_sql(query, conn)
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            chunks = []
            loaded = 0
            while True:
                rows = cursor.fetchmany(10_000)
                if not rows:
                    break
                chunk = pd.DataFrame(rows, columns=columns) if columns else pd.DataFrame(rows)
                chunks.append(chunk)
                loaded += len(chunk)
                progress_callback(loaded, loaded, f"Leyendo registros... {loaded:,}")
            df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
            progress_callback(len(df), len(df), "Datos cargados")
            return df
        finally:
            conn.close()

    def schema(self) -> list[dict]:
        conn = self._connect()
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
                    cols.append({
                        "table": t,
                        "column": row[0],
                        "type": str(row[1]),
                        "nullable": row[2] == 1,
                    })
            return cols
        finally:
            conn.close()

    def sample(self, n: int = 100) -> pd.DataFrame:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            tables = _get_table_names(cursor)
            if not tables:
                return pd.DataFrame()
            q = f"SELECT FIRST {n} * FROM {tables[0]}"
            return pd.read_sql(q, conn)
        finally:
            conn.close()
