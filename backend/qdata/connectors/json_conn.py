import pandas as pd

from qdata.connectors.base import Connector


class JSONConnector(Connector):
    def __init__(self, file_path: str, orient: str = "records", **json_kwargs):
        self.file_path = file_path
        self.orient = orient
        self.json_kwargs = json_kwargs

    def load(self, **kwargs) -> pd.DataFrame:
        params = {**self.json_kwargs, **kwargs}
        return pd.read_json(self.file_path, orient=self.orient, **params)

    def schema(self) -> list[dict]:
        df = self.load(nrows=1000)
        return [
            {"column": col, "type": str(dtype), "nullable": True}
            for col, dtype in df.dtypes.items()
        ]

    def sample(self, n: int = 100) -> pd.DataFrame:
        return self.load(nrows=n)
