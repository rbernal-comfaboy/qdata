import pandas as pd

from qdata.connectors.base import Connector


class ParquetConnector(Connector):
    def __init__(self, file_path: str, **parquet_kwargs):
        self.file_path = file_path
        self.parquet_kwargs = parquet_kwargs

    def load(self, **kwargs) -> pd.DataFrame:
        params = {**self.parquet_kwargs, **kwargs}
        return pd.read_parquet(self.file_path, **params)

    def schema(self) -> list[dict]:
        df = self.load(nrows=1000)
        return [
            {"column": col, "type": str(dtype), "nullable": True}
            for col, dtype in df.dtypes.items()
        ]

    def sample(self, n: int = 100) -> pd.DataFrame:
        return self.load(nrows=n)
