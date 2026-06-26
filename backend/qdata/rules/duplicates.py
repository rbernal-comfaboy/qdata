import pandas as pd

from qdata.rules.base import Rule, RuleResult


class DuplicateCheck(Rule):
    name = "duplicate_check"
    description = "Detecta filas duplicadas exactas y parciales"

    def __init__(self, columns: list[str] | None = None, severity: str = "error"):
        super().__init__(severity=severity)
        self.columns = columns

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        if self.columns is not None:
            cols = [c for c in self.columns if c in df.columns]
            if not cols:
                cols = list(df.columns)
            df = df[cols]

        total_rows = len(df)
        df_str = df.astype(str).fillna("")
        exact_dupes = df_str.duplicated(keep=False)
        exact_count = int(exact_dupes.sum())
        exact_pct = round((exact_count / total_rows) * 100, 2) if total_rows else 0

        details = [{"type": "exact_duplicates", "count": exact_count, "pct": exact_pct}]

        sample_failures = []
        if exact_count > 0:
            dupes = df[exact_dupes]
            dupes_str = df_str[exact_dupes]
            grouped = dupes_str.groupby(list(df_str.columns))
            for _, group in grouped:
                rows = []
                for idx in group.index:
                    rows.append({"row": int(idx), "values": dupes.loc[idx].to_dict()})
                sample_failures.append({"rows": rows})

        passed = exact_pct == 0
        recommendation = None
        if not passed:
            recommendation = "Eliminar duplicados exactos con df.drop_duplicates()"

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=total_rows,
            failed=exact_count,
            failure_pct=exact_pct,
            details=details,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )
