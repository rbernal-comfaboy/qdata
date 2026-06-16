from sqlalchemy import create_engine, inspect, text
import pandas as pd

from qdata.connectors.base import Connector


class SQLServerConnector(Connector):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string.replace("+aioodbc", "+pyodbc")
        self.engine = create_engine(self.connection_string)

    def load(self, query: str) -> pd.DataFrame:
        with self.engine.connect() as conn:
            return pd.read_sql(text(query), conn)

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
        first_table = tables[0]
        sql = text(f"SELECT TOP {n} * FROM {first_table}")
        with self.engine.connect() as conn:
            return pd.read_sql(sql, conn)
