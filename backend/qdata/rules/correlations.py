import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from qdata.rules.base import Rule, RuleResult


class CorrelationCheck(Rule):
    name = "correlation_check"
    description = "Detecta multicolinealidad (VIF) y correlaciones altas entre variables numéricas"

    def __init__(self, severity: str = "warning", vif_threshold: float = 10.0, corr_threshold: float = 0.8):
        super().__init__(severity)
        self.vif_threshold = vif_threshold
        self.corr_threshold = corr_threshold

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        numeric_df = df.select_dtypes(include=[np.number]).dropna()
        if numeric_df.shape[1] < 2:
            return RuleResult(
                rule_name=self.name,
                description=self.description,
                severity=self.severity,
                passed=True,
                total=0,
                failed=0,
                failure_pct=0,
                details=[{"message": "Se necesitan al menos 2 columnas numéricas"}],
            )

        total = numeric_df.shape[1]
        issues = []
        sample_failures = []

        corr_matrix = numeric_df.corr().abs()
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        high_corr = [(col1, col2, round(upper[col1][col2], 4))
                      for col1 in upper.columns
                      for col2 in upper.index
                      if not pd.isna(upper[col1][col2]) and upper[col1][col2] > self.corr_threshold]

        for col1, col2, val in high_corr:
            issues.append({
                "type": "HIGH_CORRELATION",
                "column_x": col1,
                "column_y": col2,
                "correlation": val,
                "threshold": self.corr_threshold,
            })
            sample_failures.append({
                "columns": f"{col1} ↔ {col2}",
                "correlation": val,
            })

        for col in numeric_df.columns:
            others = [c for c in numeric_df.columns if c != col]
            if len(others) < 1:
                continue
            try:
                X = numeric_df[others].values
                y = numeric_df[col].values
                model = LinearRegression().fit(X, y)
                r2 = model.score(X, y)
                vif = 1 / (1 - r2) if r2 < 0.999 else float("inf")

                if vif > self.vif_threshold:
                    issues.append({
                        "type": "HIGH_VIF",
                        "column": col,
                        "vif": round(vif, 2),
                        "threshold": self.vif_threshold,
                    })
            except Exception:
                pass

        failed = len(issues)
        passed = failed == 0
        recommendation = None
        if not passed:
            cols = set()
            for i in issues:
                cols.add(i.get("column_x") or i.get("column", ""))
                cols.add(i.get("column_y", ""))
            cols_str = ", ".join(sorted(c for c in cols if c))
            recommendation = (
                f"Multicolinealidad detectada en ({cols_str}). "
                f"Considerar eliminar variables correlacionadas, usar PCA, "
                f"o aplicar Regularización (Ridge/LASSO)"
            )

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=total,
            failed=failed,
            failure_pct=round(failed / total * 100, 2) if total else 0,
            details=issues,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )
