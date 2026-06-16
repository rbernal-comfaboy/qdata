"""Reglas avanzadas: completitud por fila, outliers multivariados, deriva categórica, evolución de esquema."""

import pandas as pd
import numpy as np
from qdata.rules.base import Rule, RuleResult


class RowCompletenessCheck(Rule):
    name = "row_completeness_check"
    description = "Evalúa el % de campos poblados por registro y detecta filas casi vacías (<30% de datos)"

    def __init__(self, severity: str = "warning", min_completeness_pct: float = 30.0):
        super().__init__(severity)
        self.min_completeness_pct = min_completeness_pct

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        if df.empty:
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=[{"note": "DataFrame vacío"}], recommendation=None)
        total = len(df)
        completeness = df.notna().sum(axis=1) / df.shape[1] * 100
        sparse = completeness < self.min_completeness_pct
        n_fail = int(sparse.sum())
        avg_completeness = round(float(completeness.mean()), 2)
        details = [{"total_rows": total, "avg_completeness_pct": avg_completeness, "min_completeness_pct": round(float(completeness.min()), 2), "sparse_rows": n_fail, "sparse_pct": round(n_fail / total * 100, 2)}]
        sample_failures = []
        if n_fail:
            for idx in sparse[sparse].head(10).index:
                null_cols = df.columns[df.loc[idx].isna()].tolist()
                sample_failures.append({"row": int(idx), "completeness_pct": round(float(completeness.loc[idx]), 2), "null_columns": null_cols[:10]})
        passed = n_fail == 0
        rec = None if passed else f"{n_fail} filas con <{self.min_completeness_pct}% de datos. Revisar origen o imputar valores faltantes"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=n_fail, failure_pct=round(n_fail / total * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class MultivariateOutlierCheck(Rule):
    name = "multivariate_outlier_check"
    description = "Detecta outliers multivariados usando Isolation Forest (no solo IQR univariado)"

    def __init__(self, severity: str = "warning", contamination: float = 0.05):
        super().__init__(severity)
        self.contamination = contamination

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        num_df = df.select_dtypes(include=[np.number]).dropna()
        if num_df.shape[1] < 2 or len(num_df) < 10:
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=[{"note": "Se necesitan ≥2 columnas numéricas y ≥10 filas con datos completos"}], recommendation=None)
        try:
            from sklearn.ensemble import IsolationForest
            model = IsolationForest(contamination=self.contamination, random_state=42, n_jobs=1)
            preds = model.fit_predict(num_df)
            n_fail = int((preds == -1).sum())
            passed = n_fail == 0
            details = [{"columns_used": list(num_df.columns), "total_analyzed": len(num_df), "outliers": n_fail, "pct": round(n_fail / len(num_df) * 100, 2)}]
            sample_failures = []
            if n_fail:
                outlier_idx = np.where(preds == -1)[0][:10]
                for idx in outlier_idx:
                    row_data = {c: round(float(num_df.iloc[idx][c]), 2) for c in num_df.columns[:5]}
                    sample_failures.append({"row": int(num_df.index[idx]), "values": row_data})
            rec = None if passed else f"Se detectaron {n_fail} outliers multivariados ({details[0]['pct']}%). Revisar combinaciones anómalas"
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=len(num_df), failed=n_fail, failure_pct=round(n_fail / len(num_df) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)
        except ImportError:
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=[{"note": "scikit-learn no disponible. Instalar con: pip install scikit-learn"}], recommendation=None)


class DriftCheck(Rule):
    name = "drift_check"
    description = "Detecta categorías nuevas no vistas en datos históricos (deriva categórica)"

    def __init__(self, severity: str = "warning", reference_categories: dict[str, set] | None = None):
        super().__init__(severity)
        self.reference_categories = reference_categories or {}

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        str_candidate_cols = [c for c in df.columns if pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c]) or pd.api.types.is_categorical_dtype(df[c])]
        for col in str_candidate_cols:
            current_vals = set(df[col].dropna().unique())
            if col in self.reference_categories:
                ref = self.reference_categories[col]
                new_vals = current_vals - ref
                if new_vals:
                    total += 1
                    failed += 1
                    details.append({"column": col, "new_categories": list(new_vals)[:20], "count": len(new_vals), "reference_count": len(ref)})
            else:
                # If no reference, just store current as baseline info
                total += 1
                details.append({"column": col, "note": "Sin referencia histórica. Ejecutar nuevamente con reference_categories", "unique_values": len(current_vals)})
        passed = failed == 0
        rec = None if passed else f"{failed} columna(s) con categorías nuevas. Investigar si son datos válidos o error"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class SchemaEvolutionCheck(Rule):
    name = "schema_evolution_check"
    description = "Detecta cambios en el esquema vs una referencia: columnas nuevas, eliminadas, cambios de tipo"

    def __init__(self, severity: str = "warning", reference_schema: dict[str, str] | None = None):
        super().__init__(severity)
        self.reference_schema = reference_schema or {}

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        current = {c: str(df[c].dtype) for c in df.columns}
        if not self.reference_schema:
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=[{"note": "Sin esquema de referencia. Proporcionar reference_schema={col: dtype}", "current_columns": len(current), "current_schema": current}], recommendation=None)
        ref = self.reference_schema
        added = set(current) - set(ref)
        removed = set(ref) - set(current)
        changed = {c: (ref[c], current[c]) for c in current if c in ref and ref[c] != current[c]}
        total = len(ref) + len(added)
        n_fail = len(added) + len(removed) + len(changed)
        details = [{"columns_added": list(added), "columns_removed": list(removed), "columns_type_changed": {k: f"{v[0]}→{v[1]}" for k, v in changed.items()}}]
        passed = n_fail == 0
        rec = None if passed else f"Esquema cambiado: +{len(added)} -{len(removed)} ~{len(changed)} tipos. Revisar compatibilidad"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=n_fail, failure_pct=round(n_fail / (total or 1) * 100, 2), details=details, sample_failures=[], recommendation=rec)
