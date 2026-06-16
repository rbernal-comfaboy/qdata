import numpy as np
import pandas as pd


class Profiler:
    def profile(self, df: pd.DataFrame) -> dict:
        return {
            "overview": self._overview(df),
            "numeric": self._numeric_profile(df),
            "categorical": self._categorical_profile(df),
            "temporal": self._temporal_profile(df),
        }

    def _overview(self, df: pd.DataFrame) -> dict:
        return {
            "rows": len(df),
            "columns": len(df.columns),
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
            "duplicated_rows": int(df.duplicated().sum()),
            "total_cells": df.size,
            "total_nulls": int(df.isnull().sum().sum()),
            "null_pct": round(df.isnull().sum().sum() / df.size * 100, 2) if df.size else 0,
        }

    def _numeric_profile(self, df: pd.DataFrame) -> list[dict]:
        numeric = df.select_dtypes(include=[np.number])
        results = []
        for col in numeric.columns:
            s = numeric[col].dropna()
            if len(s) == 0:
                continue
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            results.append({
                "column": col,
                "count": len(s),
                "nulls": int(numeric[col].isnull().sum()),
                "mean": round(float(s.mean()), 4),
                "std": round(float(s.std()), 4),
                "min": round(float(s.min()), 4),
                "q1": round(float(q1), 4),
                "median": round(float(s.median()), 4),
                "q3": round(float(q3), 4),
                "max": round(float(s.max()), 4),
                "skewness": round(float(s.skew()), 4),
                "kurtosis": round(float(s.kurtosis()), 4),
                "iqr": round(float(q3 - q1), 4),
            })
        return results

    def _categorical_profile(self, df: pd.DataFrame) -> list[dict]:
        cat = df.select_dtypes(include=["object", "category"])
        results = []
        for col in cat.columns:
            s = cat[col].dropna()
            value_counts = s.value_counts().head(10).to_dict()
            results.append({
                "column": col,
                "count": len(s),
                "nulls": int(cat[col].isnull().sum()),
                "unique": int(s.nunique()),
                "top_values": {str(k): int(v) for k, v in value_counts.items()},
                "cardinality_pct": round(s.nunique() / len(s) * 100, 2) if len(s) else 0,
            })
        return results

    def _temporal_profile(self, df: pd.DataFrame) -> list[dict]:
        temporal = df.select_dtypes(include=["datetime64", "datetimetz"])
        results = []
        for col in temporal.columns:
            s = temporal[col].dropna()
            if len(s) == 0:
                continue
            results.append({
                "column": col,
                "count": len(s),
                "nulls": int(temporal[col].isnull().sum()),
                "min": str(s.min()),
                "max": str(s.max()),
                "range_days": (s.max() - s.min()).days,
                "frequency": s.dt.freq or "irregular",
            })
        return results
