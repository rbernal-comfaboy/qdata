import textwrap

import pandas as pd

from qdata.rules.base import Rule, RuleResult


class CustomSQLRule(Rule):
    name = "custom_sql_rule"
    description = "Regla personalizada definida mediante consulta SQL"

    def __init__(self, severity: str = "error", sql: str = "", description: str = ""):
        super().__init__(severity)
        self._sql = sql
        self._description = description or "Regla SQL personalizada"

    @property
    def description(self) -> str:
        return self._description

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        try:
            import duckdb
            conn = duckdb.connect()
            conn.register("data", df)
            result = conn.execute(self._sql).fetchdf()
            conn.close()
        except ImportError:
            result = df.query(self._sql) if "select" not in self._sql.lower() else df.head(0)

        failed = len(result)
        passed = failed == 0
        recommendation = "Revisar registros que no cumplen la regla SQL personalizada" if not passed else None

        return RuleResult(
            rule_name=self.name,
            description=self._description,
            severity=self.severity,
            passed=passed,
            total=len(df),
            failed=failed,
            failure_pct=round(failed / len(df) * 100, 2) if len(df) else 0,
            details=[{"sql": self._sql, "failed_rows": failed}],
            sample_failures=result.head(5).to_dict("records") if failed else [],
            recommendation=recommendation,
        )


class CustomPythonRule(Rule):
    name = "custom_python_rule"
    description = "Regla personalizada definida mediante función Python"

    def __init__(self, severity: str = "error", func=None, description: str = ""):
        super().__init__(severity)
        self._func = func
        self._description = description or "Regla Python personalizada"

    @property
    def description(self) -> str:
        return self._description

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        if self._func is None:
            return RuleResult(
                rule_name=self.name,
                description=self._description,
                severity=self.severity,
                passed=True,
                total=0,
                failed=0,
                failure_pct=0,
                details=[{"message": "No se definió función de validación"}],
            )

        result = self._func(df)
        if isinstance(result, pd.Series):
            failed_mask = result
        elif isinstance(result, pd.DataFrame):
            failed_mask = result.index.isin(result.index)
        else:
            failed_mask = pd.Series([False] * len(df))

        failed = int(failed_mask.sum())
        passed = failed == 0
        recommendation = "Revisar registros que no pasan la validación personalizada" if not passed else None

        return RuleResult(
            rule_name=self.name,
            description=self._description,
            severity=self.severity,
            passed=passed,
            total=len(df),
            failed=failed,
            failure_pct=round(failed / len(df) * 100, 2) if len(df) else 0,
            details=[{"function": self._func.__name__ if hasattr(self._func, "__name__") else "lambda"}],
            sample_failures=df[failed_mask].head(5).to_dict("records") if failed else [],
            recommendation=recommendation,
        )
