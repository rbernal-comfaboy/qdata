import ctypes
import ctypes.util
from ctypes import (
    byref,
    c_char_p,
    c_int,
    c_long,
    c_short,
    c_ulong,
    c_ushort,
    c_void_p,
    create_string_buffer,
    POINTER,
)
import re
from typing import Any

import pandas as pd

from qdata.connectors.base import Connector


# ---------------------------------------------------------------------------
# ANSI ODBC wrapper via ctypes (avoids pyodbc's broken Unicode path)
# ---------------------------------------------------------------------------

_odbc = ctypes.CDLL(ctypes.util.find_library("odbc"))

if ctypes.sizeof(ctypes.c_void_p) == 8:
    SQLLEN = ctypes.c_int64
    SQLULEN = ctypes.c_uint64
else:
    SQLLEN = ctypes.c_int32
    SQLULEN = ctypes.c_uint32

_SQL_HANDLE_ENV = 1
_SQL_HANDLE_DBC = 2
_SQL_HANDLE_STMT = 3
_SQL_NULL_HANDLE = 0
_SQL_ATTR_ODBC_VERSION = 200
_SQL_OV_ODBC3 = 3
_SQL_OV_ODBC2 = 2
_SQL_NTS = -3
_SQL_DRIVER_NOPROMPT = 0
_SQL_SUCCESS = 0
_SQL_SUCCESS_WITH_INFO = 1
_SQL_NO_DATA = 100
_SQL_FETCH_NEXT = 1
_SQL_ATTR_CURRENT_CATALOG = 109

_SQL_C_CHAR = 1
_SQL_CHAR = 1
_SQL_VARCHAR = 12
_SQL_LONGVARCHAR = -1
_SQL_DROP = 1
_SQL_CLOSE = 0
_SQL_AUTOCOMMIT_ON = 1
_SQL_AUTOCOMMIT_OFF = 0
_SQL_ATTR_AUTOCOMMIT = 102
_SQL_ATTR_LOGIN_TIMEOUT = 103
_SQL_COMMIT = 0
_SQL_ROLLBACK = 1

_INFORMIX_DRIVER_PATH = "/opt/IBM/informix/lib/cli/iclit09b.so"


def _setup_odbc(odbc):
    """Configure argtypes for all ODBC functions on a loaded library."""
    odbc.SQLAllocHandle.argtypes = [c_short, c_void_p, POINTER(c_void_p)]
    odbc.SQLAllocHandle.restype = c_short
    odbc.SQLSetEnvAttr.argtypes = [c_void_p, c_int, c_void_p, c_int]
    odbc.SQLSetEnvAttr.restype = c_short
    odbc.SQLDriverConnect.argtypes = [
        c_void_p, c_void_p, c_char_p, c_short,
        c_char_p, c_short, POINTER(c_short), c_ushort,
    ]
    odbc.SQLDriverConnect.restype = c_short
    odbc.SQLDisconnect.argtypes = [c_void_p]
    odbc.SQLDisconnect.restype = c_short
    odbc.SQLFreeHandle.argtypes = [c_short, c_void_p]
    odbc.SQLFreeHandle.restype = c_short
    odbc.SQLGetDiagRec.argtypes = [
        c_short, c_void_p, c_short, c_char_p,
        POINTER(c_int), c_char_p, c_short, POINTER(c_short),
    ]
    odbc.SQLGetDiagRec.restype = c_short
    odbc.SQLExecDirect.argtypes = [c_void_p, c_char_p, c_int]
    odbc.SQLExecDirect.restype = c_short
    odbc.SQLFetch.argtypes = [c_void_p]
    odbc.SQLFetch.restype = c_short
    odbc.SQLNumResultCols.argtypes = [c_void_p, POINTER(c_short)]
    odbc.SQLNumResultCols.restype = c_short
    odbc.SQLDescribeCol.argtypes = [
        c_void_p, c_short, c_char_p, c_short,
        POINTER(c_short), POINTER(c_short), POINTER(SQLULEN),
        POINTER(c_short), POINTER(c_short),
    ]
    odbc.SQLDescribeCol.restype = c_short
    odbc.SQLGetData.argtypes = [
        c_void_p, c_short, c_short, c_void_p, c_long, POINTER(SQLLEN),
    ]
    odbc.SQLGetData.restype = c_short
    odbc.SQLBindParameter.argtypes = [
        c_void_p, c_short, c_short, c_short, c_short,
        c_ulong, c_short, c_void_p, c_long, POINTER(SQLLEN),
    ]
    odbc.SQLBindParameter.restype = c_short
    odbc.SQLSetConnectAttr.argtypes = [c_void_p, c_int, c_void_p, c_int]
    odbc.SQLSetConnectAttr.restype = c_short
    odbc.SQLEndTran.argtypes = [c_short, c_void_p, c_short]
    odbc.SQLEndTran.restype = c_short
    odbc.SQLFreeStmt.argtypes = [c_void_p, c_short]
    odbc.SQLFreeStmt.restype = c_short
    odbc.SQLNumParams.argtypes = [c_void_p, POINTER(c_short)]
    odbc.SQLNumParams.restype = c_short


_setup_odbc(_odbc)


def _raise_odbc(handle_type, handle, context="", odbc_lib=None):
    odbc = odbc_lib if odbc_lib is not None else _odbc
    state = create_string_buffer(10)
    msg = create_string_buffer(1024)
    native = c_int()
    msg_len = c_short()
    odbc.SQLGetDiagRec(
        handle_type, handle, 1, state, byref(native), msg, 1024, byref(msg_len),
    )
    s = state.value.decode() if state.value else "?"
    m = msg.value.decode() if msg.value else "Unknown error"
    raise RuntimeError(f"ODBC error [{s}]: {m} (native={native.value}){ ' [' + context + ']' if context else ''}")


def _check(ret, handle_type, handle, context="", odbc_lib=None):
    if ret == _SQL_SUCCESS or ret == _SQL_SUCCESS_WITH_INFO:
        return
    _raise_odbc(handle_type, handle, context, odbc_lib)


class _AnsiOdbcCursor:
    def __init__(self, hdbc, odbc_lib=None):
        self._odbc = odbc_lib if odbc_lib is not None else _odbc
        self._hdbc = hdbc
        self._hstmt = None
        self.description = None
        self._closed = False
        self._arraysize = 1

    def __del__(self):
        self.close()

    def close(self):
        if self._hstmt is not None:
            self._odbc.SQLFreeHandle(_SQL_HANDLE_STMT, self._hstmt)
            self._hstmt = None
        self._closed = True

    def execute(self, operation, params=None):
        if self._hstmt is not None:
            self._odbc.SQLFreeHandle(_SQL_HANDLE_STMT, self._hstmt)
            self._hstmt = None
        self.description = None

        hstmt = c_void_p()
        _check(
            self._odbc.SQLAllocHandle(_SQL_HANDLE_STMT, self._hdbc, byref(hstmt)),
            _SQL_HANDLE_DBC, self._hdbc, "SQLAllocHandle(STMT)", self._odbc,
        )
        self._hstmt = hstmt

        if params is None:
            sql_bytes = operation.encode("utf-8") if isinstance(operation, str) else operation
            _check(
                self._odbc.SQLExecDirect(hstmt, sql_bytes, _SQL_NTS),
                _SQL_HANDLE_STMT, hstmt, "SQLExecDirect", self._odbc,
            )
        else:
            if not isinstance(params, (list, tuple)):
                params = [params]
            sql = _bind_params(operation, params, hstmt)
            sql_bytes = sql.encode("utf-8") if isinstance(sql, str) else sql
            _check(
                self._odbc.SQLExecDirect(hstmt, sql_bytes, _SQL_NTS),
                _SQL_HANDLE_STMT, hstmt, "SQLExecDirect", self._odbc,
            )

        ncols = c_short(0)
        self._odbc.SQLNumResultCols(hstmt, byref(ncols))
        if ncols.value > 0:
            desc = []
            for i in range(ncols.value):
                colname = create_string_buffer(256)
                colnamelen = c_short()
                datatype = c_short()
                colsize = SQLULEN()
                decdigits = c_short()
                nullable = c_short()
                self._odbc.SQLDescribeCol(
                    hstmt, c_short(i + 1), colname, 256,
                    byref(colnamelen), byref(datatype), byref(colsize),
                    byref(decdigits), byref(nullable),
                )
                desc.append((
                    colname.value.decode() if colname.value else f"col{i}",
                    datatype.value,
                    None,  # display_size
                    colsize.value if colsize.value else 0,
                    None,  # precision
                    nullable.value if nullable.value else 0,
                    True,  # nullable
                ))
            self.description = desc

    def executemany(self, operation, seq_of_params):
        for params in seq_of_params:
            self.execute(operation, params)

    def fetchone(self):
        if self._hstmt is None:
            return None
        ret = self._odbc.SQLFetch(self._hstmt)
        if ret == _SQL_NO_DATA:
            return None
        if ret != _SQL_SUCCESS and ret != _SQL_SUCCESS_WITH_INFO:
            _raise_odbc(_SQL_HANDLE_STMT, self._hstmt, "SQLFetch", self._odbc)
        return self._read_row()

    def fetchall(self):
        rows = []
        while True:
            row = self.fetchone()
            if row is None:
                break
            rows.append(row)
        return rows

    def fetchmany(self, size=None):
        if size is None:
            size = self._arraysize
        rows = []
        for _ in range(size):
            row = self.fetchone()
            if row is None:
                break
            rows.append(row)
        return rows

    def _read_row(self):
        if self.description is None:
            return ()
        values = []
        for i in range(len(self.description)):
            buf = create_string_buffer(4096)
            indicator = SQLLEN()
            ret = self._odbc.SQLGetData(
                self._hstmt, c_short(i + 1), _SQL_C_CHAR,
                buf, 4096, byref(indicator),
            )
            if ret == _SQL_NO_DATA:
                values.append(None)
            elif indicator.value == -1:
                values.append(None)
            elif ret == _SQL_SUCCESS or ret == _SQL_SUCCESS_WITH_INFO:
                values.append(buf.value.decode("utf-8", errors="replace"))
            else:
                values.append(None)
        return tuple(values)

    def setinputsizes(self, sizes):
        pass

    def setoutputsize(self, size, column=None):
        pass

    @property
    def rowcount(self):
        return -1


def _bind_params(sql, params, hstmt):
    """Replace ? placeholders with escaped values and return the SQL string."""
    if not params:
        return sql

    parts = re.split(r"\?", sql)
    result = parts[0]
    for i, p in enumerate(params):
        if i >= len(parts) - 1:
            break
        if p is None:
            result += "NULL"
        elif isinstance(p, str):
            escaped = p.replace("'", "''")
            result += f"'{escaped}'"
        elif isinstance(p, bytes):
            escaped = p.decode("utf-8", errors="replace").replace("'", "''")
            result += f"'{escaped}'"
        elif isinstance(p, (int, float)):
            result += str(p)
        else:
            result += str(p)
        result += parts[i + 1]
    return result


class _AnsiOdbcConnection:
    def __init__(self, conn_str, autocommit=True, odbc_lib=None):
        self._odbc = odbc_lib if odbc_lib is not None else _odbc
        self._env = c_void_p()
        self._conn = c_void_p()
        self._closed = False
        self._autocommit = autocommit
        self._connect(conn_str, autocommit)

    def _connect(self, conn_str, autocommit):
        _check(
            self._odbc.SQLAllocHandle(_SQL_HANDLE_ENV, _SQL_NULL_HANDLE, byref(self._env)),
            _SQL_HANDLE_ENV, 0, "SQLAllocHandle(ENV)", self._odbc,
        )
        _check(
            self._odbc.SQLSetEnvAttr(self._env, _SQL_ATTR_ODBC_VERSION, c_void_p(_SQL_OV_ODBC3), 0),
            _SQL_HANDLE_ENV, self._env, "SQLSetEnvAttr", self._odbc,
        )
        _check(
            self._odbc.SQLAllocHandle(_SQL_HANDLE_DBC, self._env, byref(self._conn)),
            _SQL_HANDLE_ENV, self._env, "SQLAllocHandle(DBC)", self._odbc,
        )

        cs = conn_str.encode("utf-8") if isinstance(conn_str, str) else conn_str
        out = create_string_buffer(1024)
        out_len = c_short()
        _check(
            self._odbc.SQLDriverConnect(
                self._conn, None, cs, _SQL_NTS,
                out, 1024, byref(out_len), _SQL_DRIVER_NOPROMPT,
            ),
            _SQL_HANDLE_DBC, self._conn, "SQLDriverConnect", self._odbc,
        )

        if autocommit:
            self._odbc.SQLSetConnectAttr(
                self._conn, _SQL_ATTR_AUTOCOMMIT,
                c_void_p(_SQL_AUTOCOMMIT_ON), 0,
            )

    def cursor(self):
        return _AnsiOdbcCursor(self._conn, self._odbc)

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._conn:
            self._odbc.SQLDisconnect(self._conn)
            self._odbc.SQLFreeHandle(_SQL_HANDLE_DBC, self._conn)
            self._conn = None
        if self._env:
            self._odbc.SQLFreeHandle(_SQL_HANDLE_ENV, self._env)
            self._env = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def commit(self):
        if self._autocommit:
            self._odbc.SQLSetConnectAttr(
                self._conn, _SQL_ATTR_AUTOCOMMIT,
                c_void_p(_SQL_AUTOCOMMIT_OFF), 0,
            )
        self._odbc.SQLEndTran(_SQL_HANDLE_DBC, self._conn, _SQL_COMMIT)
        if self._autocommit:
            self._odbc.SQLSetConnectAttr(
                self._conn, _SQL_ATTR_AUTOCOMMIT,
                c_void_p(_SQL_AUTOCOMMIT_ON), 0,
            )

    def rollback(self):
        if self._autocommit:
            self._odbc.SQLSetConnectAttr(
                self._conn, _SQL_ATTR_AUTOCOMMIT,
                c_void_p(_SQL_AUTOCOMMIT_OFF), 0,
            )
        self._odbc.SQLEndTran(_SQL_HANDLE_DBC, self._conn, _SQL_ROLLBACK)
        if self._autocommit:
            self._odbc.SQLSetConnectAttr(
                self._conn, _SQL_ATTR_AUTOCOMMIT,
                c_void_p(_SQL_AUTOCOMMIT_ON), 0,
            )


# ---------------------------------------------------------------------------
# Informix connector
# ---------------------------------------------------------------------------

_INFORMIX_DRIVERS = [
    "IBM INFORMIX ODBC DRIVER (64-bit)",
    "IBM INFORMIX ODBC DRIVER",
    "Informix",
    "INFORMIX",
]


def _detect_driver() -> str | None:
    try:
        import pyodbc
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


def _create_informix_connection(conn_str, autocommit=True):
    """Connect to Informix using the direct driver, bypassing unixODBC."""
    direct_cs = re.sub(r'DRIVER=\{[^}]*\};', '', conn_str).strip()
    odbc = ctypes.CDLL(_INFORMIX_DRIVER_PATH)
    _setup_odbc(odbc)
    conn = _AnsiOdbcConnection(direct_cs, autocommit=autocommit, odbc_lib=odbc)
    m = re.search(r'DATABASE=([^;]+)', conn_str)
    if m:
        db_name = m.group(1).encode("utf-8")
        conn._odbc.SQLSetConnectAttr(
            conn._conn, _SQL_ATTR_CURRENT_CATALOG,
            c_char_p(db_name), _SQL_NTS,
        )
    return conn


class InformixConnector(Connector):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    def _connect(self):
        return _create_informix_connection(self.connection_string)

    def load(self, query: str, progress_callback=None, nrows: int = 0) -> pd.DataFrame:
        if nrows and not re.search(r'\bFIRST\b', query[:80], re.IGNORECASE):
            query = f"SELECT FIRST {nrows} * FROM ({query}) AS _qdata_preview_"
        try:
            df = _load_subprocess(self.connection_string, query)
            if progress_callback:
                progress_callback(len(df), len(df), "Datos cargados")
            return df
        except Exception as e:
            raise RuntimeError(f"Error loading Informix data: {e}")

    def schema(self) -> list[dict]:
        return get_schema_subprocess(self.connection_string)

    def sample(self, n: int = 100) -> pd.DataFrame:
        try:
            tables = get_tables_subprocess(self.connection_string)
            if not tables:
                return pd.DataFrame()
            q = f"SELECT FIRST {n} * FROM {tables[0]['name']}"
            return _load_subprocess(self.connection_string, q)
        except Exception as e:
            raise RuntimeError(f"Error sampling Informix data: {e}")


# ---------------------------------------------------------------------------
# Subprocess helpers (avoids segfault when ODBC driver runs inside uvicorn)
# ---------------------------------------------------------------------------

import subprocess, sys, json, textwrap


def _load_subprocess(conn_str: str, query: str, timeout: int = 120) -> pd.DataFrame:
    """Run a SELECT query in a subprocess and return results as DataFrame."""
    import base64
    encoded = base64.b64encode(query.encode()).decode()
    script = (
        "import sys\n"
        "sys.path.insert(0, '/app')\n"
        "from qdata.connectors.informix import _create_informix_connection\n"
        "import csv, io, base64\n"
        "c = _create_informix_connection(%r, autocommit=True)\n"
        "try:\n"
        "    cur = c.cursor()\n"
        "    q = base64.b64decode('%s').decode()\n"
        "    cur.execute(q)\n"
        "    cols = [d[0] for d in (cur.description or [])]\n"
        "    buf = io.StringIO()\n"
        "    w = csv.writer(buf)\n"
        "    if cols:\n"
        "        w.writerow(cols)\n"
        "    for row in cur.fetchall():\n"
        "        w.writerow(row)\n"
        "    print(buf.getvalue())\n"
        "finally:\n"
        "    c.close()\n"
    ) % (conn_str, encoded)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Informix subprocess failed: {result.stderr}")
    if not result.stdout.strip():
        return pd.DataFrame()
    import io
    return pd.read_csv(io.StringIO(result.stdout))


def _informix_subprocess(code: str, conn_str: str, timeout: int = 60) -> str:
    """Run Informix ODBC code in a subprocess to avoid driver segfaults."""
    wrapped = textwrap.indent(code.strip(), "    ")
    script = (
        "import sys\n"
        "sys.path.insert(0, '/app')\n"
        "from qdata.connectors.informix import _create_informix_connection, _get_table_names\n"
        "import json\n"
        "c = _create_informix_connection(%r, autocommit=True)\n"
        "try:\n"
        "    cur = c.cursor()\n"
        "%s\n"
        "finally:\n"
        "    c.close()\n"
    ) % (conn_str, wrapped)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Informix subprocess failed: {result.stderr}")
    return result.stdout


def get_tables_subprocess(conn_str: str) -> list[dict]:
    stdout = _informix_subprocess("""
tables = _get_table_names(cur)
print(json.dumps([{"name": t, "row_count": None} for t in tables]))
""", conn_str)
    return json.loads(stdout)


def get_schema_subprocess(conn_str: str) -> list[dict]:
    """Return all tables and their columns (for the Connector.schema() interface)."""
    stdout = _informix_subprocess("""
tables = _get_table_names(cur)
all_cols = []
for t in tables:
    cur.execute(
        "SELECT c.colname, c.coltype, CASE WHEN c.coltype >= 256 THEN 1 ELSE 0 END "
        "FROM syscolumns c, systables t2 "
        "WHERE c.tabid = t2.tabid AND t2.tabname = ? AND t2.tabid >= 100",
        t,
    )
    for row in cur.fetchall():
        all_cols.append({"table": t, "column": row[0], "type": str(row[1]), "nullable": row[2] == 1})
print(json.dumps(all_cols))
""", conn_str, timeout=300)
    return json.loads(stdout)


def get_columns_subprocess(conn_str: str, table_name: str) -> list[dict]:
    stdout = _informix_subprocess(f"""
cur.execute(
    "SELECT c.colname, c.coltype, CASE WHEN c.coltype >= 256 THEN 1 ELSE 0 END "
    "FROM syscolumns c, systables t "
    "WHERE c.tabid = t.tabid AND t.tabname = ? AND t.tabid >= 100",
    {table_name!r},
)
cols = []
for row in cur.fetchall():
    cols.append({{"name": row[0], "type": str(row[1]), "nullable": row[2] == 1}})
print(json.dumps(cols))
""", conn_str)
    return json.loads(stdout)
