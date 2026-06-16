import pandas as pd

from qdata.connectors.base import Connector


class ExcelConnector(Connector):
    def __init__(self, file_path: str, sheet_name: str | int = 0, **excel_kwargs):
        self.file_path = file_path
        self.sheet_name = sheet_name
        self.excel_kwargs = excel_kwargs

    def load(self, **kwargs) -> pd.DataFrame:
        params = {**self.excel_kwargs, **kwargs}
        return pd.read_excel(self.file_path, sheet_name=self.sheet_name, **params)

    def schema(self) -> list[dict]:
        df = self.load(nrows=1000)
        return [
            {"column": col, "type": str(dtype), "nullable": True}
            for col, dtype in df.dtypes.items()
        ]

    def sample(self, n: int = 100) -> pd.DataFrame:
        return self.load(nrows=n)
