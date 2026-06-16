import pandas as pd

from qdata.rules.base import Rule, RuleResult


class CardinalityCheck(Rule):
    name = "cardinality_check"
    description = "Detecta cardinalidad anómala (alta o baja) en cada columna"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total_rows = len(df)
        issues = 0
        details = []
        sample_failures = []

        for col in df.columns:
            nunique = df[col].nunique()
            pct = round(nunique / total_rows * 100, 2) if total_rows else 0

            if nunique == 1:
                issues += 1
                details.append({
                    "column": col,
                    "unique_values": nunique,
                    "total": total_rows,
                    "pct": pct,
                    "issue": "SINGLE_VALUE - columna constante, sin información",
                })
                sample_failures.append({"column": col, "warning": "Todos los valores son iguales"})
            elif pct > 95 and df[col].dtype == "object":
                issues += 1
                details.append({
                    "column": col,
                    "unique_values": nunique,
                    "total": total_rows,
                    "pct": pct,
                    "issue": "HIGH_CARDINALITY - posible columna ID o timestamp",
                })
                sample_failures.append({"column": col, "warning": "Cardinalidad muy alta (>95%)"})

        passed = issues == 0
        recommendation = None
        if not passed:
            cols = ", ".join(d["column"] for d in details[:3])
            recommendation = f"Revisar cardinalidad en ({cols}). Columnas constantes pueden eliminarse; alta cardinalidad puede ser clave primaria"

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=len(df.columns),
            failed=issues,
            failure_pct=round(issues / len(df.columns) * 100, 2) if len(df.columns) else 0,
            details=details,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )
