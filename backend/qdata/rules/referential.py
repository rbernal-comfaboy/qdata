import pandas as pd

from qdata.rules.base import Rule, RuleResult


class ReferentialIntegrityCheck(Rule):
    name = "referential_integrity_check"
    description = "Verifica integridad referencial entre columnas de un mismo dataset"

    def __init__(self, severity: str = "error", references: list[tuple[str, str]] | None = None):
        super().__init__(severity)
        self.references = references or []

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0
        issues = 0
        details = []
        sample_failures = []

        for child_col, parent_col in self.references:
            if child_col not in df.columns or parent_col not in df.columns:
                continue
            child_vals = df[child_col].dropna()
            parent_vals = set(df[parent_col].dropna().unique())
            total += len(child_vals)
            orphans = child_vals[~child_vals.isin(parent_vals)]
            n_orphans = len(orphans)
            if n_orphans > 0:
                issues += n_orphans
                details.append({
                    "child_column": child_col,
                    "parent_column": parent_col,
                    "orphans": n_orphans,
                    "total": len(child_vals),
                    "pct": round(n_orphans / len(child_vals) * 100, 2),
                })
                for val in orphans.head(5):
                    sample_failures.append({
                        "column": child_col,
                        "value": str(val),
                        "missing_in": parent_col,
                    })

        passed = issues == 0
        recommendation = None
        if not passed:
            refs = ", ".join(f"{c}→{p}" for c, p in self.references[:3])
            recommendation = f"Revisar integridad referencial: ({refs}). Valores huérfanos no tienen correspondencia en la tabla padre"

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=total,
            failed=issues,
            failure_pct=round(issues / total * 100, 2) if total else 0,
            details=details,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )
