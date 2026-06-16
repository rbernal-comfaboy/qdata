import pandas as pd

from qdata.rules.base import Rule, RuleResult


class TypeCheck(Rule):
    name = "type_check"
    description = "Verifica coherencia de tipos de datos en cada columna"

    def __init__(self, severity: str = "error", expected_types: dict[str, str] | None = None):
        super().__init__(severity)
        self.expected_types = expected_types or {}

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total_cols = len(df.columns)
        issues = []
        sample_failures = []

        for col in df.columns:
            dtype = str(df[col].dtype)
            non_null = df[col].dropna()
            if len(non_null) == 0:
                continue

            inferred = self._infer_actual_type(non_null)
            expected = self.expected_types.get(col, inferred)
            if inferred != expected:
                issues.append({
                    "column": col,
                    "declared_type": dtype,
                    "inferred_type": inferred,
                    "expected_type": expected,
                })
                sample_failures.append({"column": col, "sample_value": str(non_null.iloc[0])})

            if dtype == "object":
                mixed = self._check_mixed_types(non_null)
                if mixed:
                    issues.append({
                        "column": col,
                        "declared_type": dtype,
                        "inferred_type": "mixed",
                        "mixed_types": mixed,
                    })

        failed = len(issues)
        passed = failed == 0
        recommendation = None
        if not passed:
            cols = ", ".join(i["column"] for i in issues[:3])
            recommendation = f"Revisar tipos en ({cols}). Usar pd.to_datetime(), pd.to_numeric() con errors='coerce'"

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=total_cols,
            failed=failed,
            failure_pct=round(failed / total_cols * 100, 2) if total_cols else 0,
            details=issues,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )

    def _infer_actual_type(self, series: pd.Series) -> str:
        sample = series.head(100)
        try:
            pd.to_numeric(sample)
            return "numeric"
        except (ValueError, TypeError):
            pass
        try:
            pd.to_datetime(sample, infer_datetime_format=True)
            return "datetime"
        except (ValueError, TypeError):
            pass
        return "text"

    def _check_mixed_types(self, series: pd.Series) -> list[str]:
        types = set()
        for v in series.head(200):
            types.add(type(v).__name__)
        return list(types - {"str", "NoneType"}) if len(types) > 1 else []
