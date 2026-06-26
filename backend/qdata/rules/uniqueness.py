import pandas as pd

from qdata.rules.base import Rule, RuleResult


class UniqueCheck(Rule):
    name = "unique_check"
    description = "Verifica unicidad de columnas candidatas a clave primaria"

    def __init__(self, severity: str = "error", key_columns: list[str] | None = None):
        super().__init__(severity)
        self.key_columns = key_columns

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        if self.key_columns:
            cols = [c for c in self.key_columns if c in df.columns]
        else:
            cols = list(df.columns[:min(3, len(df.columns))])

        total = len(df) * len(cols)
        issues = 0
        details = []
        sample_failures = []

        for col in cols:
            dupes = df[col].duplicated(keep=False)
            n_dupes = int(dupes.sum())
            if n_dupes > 0:
                issues += n_dupes
                details.append({
                    "column": col,
                    "duplicates": n_dupes,
                    "total": len(df),
                    "pct": round(n_dupes / len(df) * 100, 2),
                    "unique_values": int(df[col].nunique()),
                })
                for idx in df[dupes].drop_duplicates(subset=col).index:
                    sample_failures.append({
                        "column": col,
                        "row": int(idx),
                        "value": str(df.loc[idx, col]),
                    })

        if self.key_columns:
            existing = [c for c in self.key_columns if c in df.columns]
            if existing:
                combo_dupes = df.duplicated(subset=existing, keep=False)
                combo_count = int(combo_dupes.sum())
                if combo_count > 0:
                    issues += combo_count
                    details.append({
                        "columns": existing,
                        "composite_duplicates": combo_count,
                        "total": len(df),
                        "pct": round(combo_count / len(df) * 100, 2),
                    })

        passed = issues == 0
        recommendation = None
        if not passed:
            cols_str = ", ".join(d.get("column", str(d.get("columns", ""))) for d in details[:3])
            recommendation = f"Revisar unicidad en ({cols_str}). Eliminar duplicados o verificar lógica de clave primaria"

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
