import re
from pathlib import Path

import pandas as pd

from qdata.connectors.base import Connector


_ENCODINGS = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]
_SEPARATORS = [",", ";", "\t", "|"]


def _detect_encoding(path: str) -> str:
    import codecs
    with open(path, "rb") as f:
        raw = f.read(8192)
    for enc in _ENCODINGS:
        try:
            codecs.decode(raw, enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "utf-8"


def _detect_separator(path: str, encoding: str) -> str:
    import csv
    with open(path, newline="", encoding=encoding) as f:
        sample = f.read(8192)
    try:
        dialect = csv.Sniffer().sniff(sample)
        return dialect.delimiter
    except csv.Error:
        scores = {sep: sample.count(sep) for sep in _SEPARATORS}
        return max(scores, key=scores.get) if max(scores.values()) > 0 else ","


class CSVConnector(Connector):
    def __init__(self, file_path: str, **csv_kwargs):
        self.file_path = file_path
        self.csv_kwargs = csv_kwargs

    def load(self, **kwargs) -> pd.DataFrame:
        params = {**self.csv_kwargs, **kwargs}
        self._fill_detected(params)
        try:
            return pd.read_csv(self.file_path, **params)
        except (UnicodeDecodeError, pd.errors.ParserError) as e:
            if isinstance(e, UnicodeDecodeError):
                for enc in [e for e in _ENCODINGS if e != params.get("encoding", "utf-8")]:
                    try:
                        params["encoding"] = enc
                        return pd.read_csv(self.file_path, **params)
                    except UnicodeDecodeError:
                        continue
            raise

    def schema(self) -> list[dict]:
        df = self.load(nrows=1000)
        return [
            {"column": col, "type": str(dtype), "nullable": True, "inferred": True}
            for col, dtype in df.dtypes.items()
        ]

    def sample(self, n: int = 100) -> pd.DataFrame:
        return self.load(nrows=n)

    def _fill_detected(self, params: dict) -> None:
        if "encoding" not in params:
            params["encoding"] = _detect_encoding(self.file_path)
        if "sep" not in params:
            params["sep"] = _detect_separator(self.file_path, params["encoding"])
