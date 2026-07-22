import pandas as pd

from qdata.rules.base import Rule, RuleResult


def _row_values(df: pd.DataFrame, idx: int) -> dict:
    row = df.loc[idx]
    return {col: (v.item() if hasattr(v, 'item') else v) for col, v in row.items()}


class RangeCheck(Rule):
    name = "range_check"
    description = "Detecta valores fuera de rango y outliers mediante IQR y z-score"

    def __init__(self, severity: str = "warning", z_score_threshold: float = 3.0):
        super().__init__(severity)
        self.z_score_threshold = z_score_threshold

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        duckdb_conn = kwargs.get("duckdb_conn")
        if duckdb_conn is not None:
            return self._execute_duckdb(duckdb_conn, df.columns)
        return self._execute_pandas(df)

    def _execute_duckdb(self, conn, columns: list[str]) -> RuleResult:
        numeric_cols = []
        for col in columns:
            dtype = conn.execute(f"SELECT typeof(\"{col}\") FROM data LIMIT 1").fetchone()[0]
            if dtype.startswith(("INT", "BIGINT", "SMALLINT", "TINYINT", "FLOAT", "DOUBLE", "DECIMAL", "HUGEINT", "UBIGINT", "INTEGER")):
                numeric_cols.append(col)

        total_values = 0
        issue_count = 0
        details = []
        sample_failures = []

        for col in numeric_cols:
            quoted = f'"{col}"'
            stats = conn.execute(
                f"SELECT count(*), min({quoted}), max({quoted}), avg({quoted}), stddev({quoted}) FROM data WHERE {quoted} IS NOT NULL"
            ).fetchone()
            count, mn, mx, avg, std = stats
            if count is None or count < 4:
                continue
            count = int(count)
            total_values += count

            perc = conn.execute(
                f"SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY {quoted}), percentile_cont(0.75) WITHIN GROUP (ORDER BY {quoted}) FROM data WHERE {quoted} IS NOT NULL"
            ).fetchone()
            q1, q3 = float(perc[0]), float(perc[1])
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            outliers = conn.execute(
                f"SELECT count(*) FROM data WHERE {quoted} IS NOT NULL AND ({quoted} < {lower} OR {quoted} > {upper})"
            ).fetchone()
            n_outliers = int(outliers[0])

            if std and float(std) > 0:
                z_out = conn.execute(
                    f"SELECT count(*) FROM data WHERE {quoted} IS NOT NULL AND ABS({quoted} - {avg}) / {std} > {self.z_score_threshold}"
                ).fetchone()
                n_outliers = max(n_outliers, int(z_out[0]))

            pct = round(n_outliers / count * 100, 2) if count else 0
            if n_outliers > 0:
                issue_count += n_outliers
                details.append({
                    "column": col,
                    "outliers": n_outliers,
                    "pct": pct,
                    "min": round(float(mn), 4),
                    "max": round(float(mx), 4),
                    "q1": round(q1, 4),
                    "q3": round(q3, 4),
                    "lower_bound": round(lower, 4),
                    "upper_bound": round(upper, 4),
                })
                samples = conn.execute(
                    f"SELECT rowid, {quoted} FROM data WHERE {quoted} IS NOT NULL AND ({quoted} < {lower} OR {quoted} > {upper}) LIMIT 500"
                ).fetchall()
                for row_data in samples:
                    sample_failures.append({"column": col, "row": int(row_data[0]), "value": float(row_data[1])})

        failed = issue_count
        passed = failed == 0
        recommendation = None
        if not passed:
            cols = ", ".join(d["column"] for d in details[:3])
            recommendation = (
                f"Revisar outliers en ({cols}). Considerar winsorización "
                f"al percentil 99 o validar si son errores de captura"
            )

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=total_values,
            failed=failed,
            failure_pct=round(failed / total_values * 100, 2) if total_values else 0,
            details=details,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )

    def _execute_pandas(self, df: pd.DataFrame) -> RuleResult:
        import numpy as np
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        issue_count = 0
        total_values = 0
        details = []
        sample_failures = []

        for col in numeric_cols:
            series = df[col].dropna()
            total_values += len(series)
            if len(series) < 4:
                continue

            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr

            iqr_outliers = series[(series < lower) | (series > upper)]
            mean, std = series.mean(), series.std()
            if std > 0:
                z_scores = np.abs((series - mean) / std)
                z_outliers = series[z_scores > self.z_score_threshold]
            else:
                z_outliers = pd.Series(dtype=float)

            combined = pd.concat([iqr_outliers, z_outliers]).drop_duplicates()
            n_outliers = len(combined)
            pct = round(n_outliers / len(series) * 100, 2)

            if n_outliers > 0:
                issue_count += n_outliers
                details.append({
                    "column": col,
                    "outliers": n_outliers,
                    "pct": pct,
                    "min": round(float(series.min()), 4),
                    "max": round(float(series.max()), 4),
                    "q1": round(float(q1), 4),
                    "q3": round(float(q3), 4),
                    "lower_bound": round(float(lower), 4),
                    "upper_bound": round(float(upper), 4),
                })
                for idx in combined.index:
                    sample_failures.append({
                        "column": col,
                        "row": int(idx),
                        "value": float(series.loc[idx]),
                        "values": _row_values(df, idx),
                    })

        failed = issue_count
        passed = failed == 0
        recommendation = None
        if not passed:
            cols = ", ".join(d["column"] for d in details[:3])
            recommendation = (
                f"Revisar outliers en ({cols}). Considerar winsorización "
                f"al percentil 99 o validar si son errores de captura"
            )

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=total_values,
            failed=failed,
            failure_pct=round(failed / total_values * 100, 2) if total_values else 0,
            details=details,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )
