import numpy as np
import pandas as pd
from scipy.stats import shapiro, skew, kurtosis

from qdata.rules.base import Rule, RuleResult


class DistributionCheck(Rule):
    name = "distribution_check"
    description = "Evalúa distribuciones estadísticas: normalidad, asimetría y curtosis"

    def __init__(self, severity: str = "warning", shapiro_threshold: float = 0.05):
        super().__init__(severity)
        self.shapiro_threshold = shapiro_threshold

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        issues = 0
        details = []
        sample_failures = []

        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) < 4 or len(series) > 5000:
                continue

            stat, p_value = shapiro(series)
            skew_val = float(skew(series))
            kurt_val = float(kurtosis(series))

            flags = []
            if p_value < self.shapiro_threshold:
                flags.append("NON_NORMAL")
            if abs(skew_val) > 1:
                flags.append(f"SKEWED({skew_val:.2f})")
            if abs(kurt_val) > 3:
                flags.append(f"HIGH_KURTOSIS({kurt_val:.2f})")

            if flags:
                issues += 1
                details.append({
                    "column": col,
                    "shapiro_stat": round(stat, 4),
                    "shapiro_pvalue": round(p_value, 6),
                    "skewness": round(skew_val, 4),
                    "kurtosis": round(kurt_val, 4),
                    "flags": flags,
                    "count": len(series),
                })
                sample_failures.append({"column": col, "flags": flags})

        passed = issues == 0
        recommendation = None
        if not passed:
            cols = ", ".join(d["column"] for d in details[:3])
            recommendation = (
                f"Distribuciones no normales en ({cols}). "
                f"Considerar transformación logarítmica o Box-Cox antes de modelos paramétricos"
            )

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=len(numeric_cols),
            failed=issues,
            failure_pct=round(issues / len(numeric_cols) * 100, 2) if len(numeric_cols) else 0,
            details=details,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )
