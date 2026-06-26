from sqlalchemy import create_engine, inspect, text
import pandas as pd

from qdata.connectors.base import Connector

_FETCH_SIZE = 10_000


class SQLiteConnector(Connector):
    def __init__(self, path: str):
        self.connection_string = f"sqlite:///{path}"
        self.path = path
        self.engine = create_engine(self.connection_string)

    def load(self, query: str, progress_callback=None) -> pd.DataFrame:
        with self.engine.connect() as conn:
            if not progress_callback:
                return pd.read_sql(text(query), conn)
            result = conn.execution_options(stream_results=True).execute(text(query))
            chunks = []
            loaded = 0
            while True:
                rows = result.fetchmany(_FETCH_SIZE)
                if not rows:
                    break
                chunk = pd.DataFrame(rows, columns=result.keys())
                chunks.append(chunk)
                loaded += len(chunk)
                progress_callback(loaded, loaded, f"Leyendo registros... {loaded:,}")
            df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
            progress_callback(len(df), len(df), "Datos cargados")
            return df

    def schema(self) -> list[dict]:
        inspector = inspect(self.engine)
        cols = []
        for table in inspector.get_table_names():
            for col in inspector.get_columns(table):
                cols.append({
                    "table": table,
                    "column": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                })
        return cols

    def sample(self, n: int = 100) -> pd.DataFrame:
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        if not tables:
            return pd.DataFrame()
        query = f"SELECT * FROM {tables[0]} LIMIT {n}"
        return self.load(query)
