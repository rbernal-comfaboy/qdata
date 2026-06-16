import pandas as pd
import pytest
import tempfile
import os

from qdata.connectors.csv_conn import CSVConnector
from qdata.connectors.json_conn import JSONConnector
from qdata.connectors.parquet_conn import ParquetConnector


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["A", "B", "C"],
        "value": [10.5, 20.3, 30.7],
    })


class TestCSVConnector:
    def test_load_csv(self, sample_df):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            sample_df.to_csv(f, index=False)
            f.flush()
            connector = CSVConnector(f.name)
            loaded = connector.load()
            os.unlink(f.name)
            assert len(loaded) == 3
            assert list(loaded.columns) == ["id", "name", "value"]

    def test_schema(self, sample_df):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            sample_df.to_csv(f.name, index=False)
            f.flush()
            connector = CSVConnector(f.name)
            schema = connector.schema()
            os.unlink(f.name)
            assert len(schema) == 3


class TestJSONConnector:
    def test_load_json(self, sample_df):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            sample_df.to_json(f, orient="records")
            f.flush()
            connector = JSONConnector(f.name)
            loaded = connector.load()
            os.unlink(f.name)
            assert len(loaded) == 3


class TestParquetConnector:
    def test_load_parquet(self, sample_df):
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            fname = f.name
            sample_df.to_parquet(fname, index=False)
            connector = ParquetConnector(fname)
            loaded = connector.load()
            os.unlink(fname)
            assert len(loaded) == 3
