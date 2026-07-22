import pandas as pd

from qdata.rules.base import Rule, RuleResult


def _row_values(df: pd.DataFrame, idx: int) -> dict:
    row = df.loc[idx]
    return {col: (v.item() if hasattr(v, 'item') else v) for col, v in row.items()}


class NullCheck(Rule):
    name = "null_check"
    description = "Detecta valores nulos y vacíos en todas las columnas"
    MAX_NULL_PCT = 5.0

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        duckdb_conn = kwargs.get("duckdb_conn")
        if duckdb_conn is not None:
            return self._execute_duckdb(duckdb_conn, df.columns)
        return self._execute_pandas(df)

    def _execute_duckdb(self, conn, columns: list[str]) -> RuleResult:
        total_rows = conn.execute("SELECT count(*) FROM data").fetchone()[0]
        total_cells = total_rows * len(columns)

        details = []
        sample_failures = []
        total_null = 0

        for col in columns:
            quoted = f'"{col}"'
            row = conn.execute(
                f"SELECT count(*) FILTER (WHERE {quoted} IS NULL OR (typeof({quoted}) = 'VARCHAR' AND TRIM({quoted}) = '')) FROM data"
            ).fetchone()
            n = int(row[0])
            if n > 0:
                total_null += n
                details.append({"column": col, "nulls": n, "pct": round(n / total_rows * 100, 2)})

        failure_pct = round((total_null / total_cells) * 100, 2) if total_cells else 0
        passed = failure_pct <= self.MAX_NULL_PCT

        for col in columns:
            if any(d["column"] == col for d in details):
                nulls = conn.execute(
                    f"SELECT rowid, \"{col}\" FROM data WHERE \"{col}\" IS NULL OR (typeof(\"{col}\") = 'VARCHAR' AND TRIM(\"{col}\") = '') LIMIT 500"
                ).fetchall()
                for row_data in nulls:
                    sample_failures.append({"column": col, "row": int(row_data[0]), "value": row_data[1]})

        recommendation = None
        if not passed and details:
            cols = ", ".join(d["column"] for d in details[:3])
            recommendation = (
                f"Reemplazar nulos en ({cols}) con valor por defecto "
                f"o imputar con media/mediana/moda según el tipo de dato"
            )

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=int(total_cells),
            failed=int(total_null),
            failure_pct=failure_pct,
            details=details,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )

    def _execute_pandas(self, df: pd.DataFrame) -> RuleResult:
        total_cells = df.size
        total_rows = len(df)
        null_counts = df.isnull().sum()
        empty_counts = df.apply(
            lambda col: col.astype(str).str.strip().eq("").sum() if col.dtype == "object" else 0
        )
        total_null = int(null_counts.sum() + empty_counts.sum())
        failure_pct = round((total_null / total_cells) * 100, 2) if total_cells else 0

        details = []
        for col in df.columns:
            n = int(null_counts[col]) + int(empty_counts[col])
            if n > 0:
                details.append({"column": col, "nulls": n, "pct": round(n / total_rows * 100, 2)})

        sample_failures = []
        for col in df.columns:
            if null_counts[col] > 0:
                indices = df[df[col].isnull()].index[:500].tolist()
                for idx in indices:
                    sample_failures.append({"column": col, "row": int(idx), "value": None, "values": _row_values(df, idx)})
            if empty_counts[col] > 0:
                empty_mask = df[col].astype(str).str.strip().eq("")
                empty_indices = df[empty_mask].index[:500].tolist()
                for idx in empty_indices:
                    if idx not in df[df[col].isnull()].index:
                        sample_failures.append({"column": col, "row": int(idx), "value": "", "values": _row_values(df, idx)})

        passed = failure_pct <= self.MAX_NULL_PCT
        recommendation = None
        if not passed and details:
            cols = ", ".join(d["column"] for d in details[:3])
            recommendation = (
                f"Reemplazar nulos en ({cols}) con valor por defecto "
                f"o imputar con media/mediana/moda según el tipo de dato"
            )

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=int(total_cells),
            failed=int(total_null),
            failure_pct=failure_pct,
            details=details,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )
