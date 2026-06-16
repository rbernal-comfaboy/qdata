import pandas as pd

from qdata.rules.base import Rule, RuleResult


class DuplicateCheck(Rule):
    name = "duplicate_check"
    description = "Detecta filas duplicadas exactas y parciales"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total_rows = len(df)
        exact_dupes = df.duplicated(keep=False)
        exact_count = int(exact_dupes.sum())
        exact_pct = round((exact_count / total_rows) * 100, 2) if total_rows else 0

        details = [{"type": "exact_duplicates", "count": exact_count, "pct": exact_pct}]

        sample_failures = []
        if exact_count > 0:
            dupes = df[exact_dupes].drop_duplicates().head(5)
            for idx, row in dupes.iterrows():
                sample_failures.append({"row": int(idx), "values": row.to_dict()})

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
