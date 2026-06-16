import re

import pandas as pd

from qdata.rules.base import Rule, RuleResult

COMMON_PATTERNS = {
    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "phone": r"^\+?[\d\s\-\(\)]{7,20}$",
    "url": r"^https?://[^\s]+$",
    "date_iso": r"^\d{4}-\d{2}-\d{2}$",
    "rfc_mx": r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$",
    "curp_mx": r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[0-9A-Z]\d$",
}


class PatternCheck(Rule):
    name = "pattern_check"
    description = "Valida formato de columnas contra patrones regex (email, teléfono, RFC, etc.)"

    def __init__(self, severity: str = "error", column_patterns: dict[str, str] | None = None):
        super().__init__(severity)
        self.column_patterns = column_patterns or {}

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        issues = 0
        total_checks = 0
        details = []
        sample_failures = []

        for col, pattern_name in self.column_patterns.items():
            if col not in df.columns:
                continue
            regex = COMMON_PATTERNS.get(pattern_name, pattern_name)
            series = df[col].dropna().astype(str)
            total_checks += len(series)
            mask = series.str.match(regex)
            failed = int((~mask).sum())

            if failed > 0:
                issues += failed
                details.append({
                    "column": col,
                    "pattern": pattern_name,
                    "failed": failed,
                    "total": len(series),
                    "pct": round(failed / len(series) * 100, 2),
                })
                for idx in series[~mask].head(5).index:
                    sample_failures.append({
                        "column": col,
                        "row": int(idx),
                        "value": str(series.loc[idx]),
                    })

        if not self.column_patterns:
            details = []
            for col in df.select_dtypes(include=["object"]).columns:
                series = df[col].dropna().astype(str)
                if len(series) < 3:
                    continue
                total_checks += len(series)
                for pname, regex in COMMON_PATTERNS.items():
                    mask = series.str.match(regex)
                    matched = int(mask.sum())
                    if matched > len(series) * 0.8:
                        issues += int((~mask).sum())
                        details.append({
                            "column": col,
                            "pattern": pname,
                            "matched": matched,
                            "total": len(series),
                            "pct_match": round(matched / len(series) * 100, 2),
                        })
                        break

        passed = issues == 0
        recommendation = None
        if not passed and details:
            cols = ", ".join(d["column"] for d in details[:3])
            recommendation = f"Corregir formato en ({cols}). Estandarizar con regex o librerías de validación"

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=total_checks or len(df.columns),
            failed=issues,
            failure_pct=round(issues / (total_checks or 1) * 100, 2),
            details=details,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )
