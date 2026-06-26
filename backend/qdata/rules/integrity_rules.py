"""Reglas de integridad: anomalía de volumen, integridad secuencial, llaves foráneas ausentes."""

import pandas as pd
import numpy as np
from qdata.rules.base import Rule, RuleResult


class VolumeAnomalyCheck(Rule):
    name = "volume_anomaly_check"
    description = "Detecta anomalías en el volumen de filas vs el promedio histórico"

    def __init__(self, severity: str = "warning", expected_rows: int | None = None, tolerance_pct: float = 20.0):
        super().__init__(severity)
        self.expected_rows = expected_rows
        self.tolerance_pct = tolerance_pct

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        actual = len(df)
        if self.expected_rows is None:
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=1, failed=0, failure_pct=0, details=[{"actual_rows": actual, "note": "Sin valor esperado. Configurar expected_rows para activar detección"}], recommendation=None)
        deviation = abs(actual - self.expected_rows) / self.expected_rows * 100
        passed = deviation <= self.tolerance_pct
        details = [{"actual_rows": actual, "expected_rows": self.expected_rows, "deviation_pct": round(deviation, 2), "tolerance_pct": self.tolerance_pct}]
        n_fail = 0 if passed else 1
        rec = None if passed else f"Volumen anómalo: {actual} filas vs {self.expected_rows} esperadas (desviación {deviation:.1f}%)"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=1, failed=n_fail, failure_pct=round(deviation, 2), details=details, sample_failures=[], recommendation=rec)


class SequentialIntegrityCheck(Rule):
    name = "sequential_integrity_check"
    description = "Verifica que IDs secuenciales no tengan saltos (detecta eliminaciones o errores de generación)"

    def __init__(self, severity: str = "warning", id_columns: list[str] | None = None):
        super().__init__(severity)
        self.id_columns = id_columns or []

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        candidates = self.id_columns or [c for c in df.columns if any(kw in c.lower() for kw in ["id", "folio", "numero", "number", "consecutivo"]) and df[c].dropna().dtype in (np.int64, np.float64, int, float)]
        for col in candidates:
            if col not in df.columns:
                continue
            series = pd.to_numeric(df[col], errors="coerce").dropna().astype(int)
            if len(series) < 5:
                continue
            total += 1
            sorted_vals = sorted(series.unique())
            expected = list(range(sorted_vals[0], sorted_vals[-1] + 1))
            missing = set(expected) - set(sorted_vals)
            n_fail = len(missing)
            if n_fail:
                failed += n_fail
                details.append({"column": col, "gaps": n_fail, "from": sorted_vals[0], "to": sorted_vals[-1], "unique_values": len(sorted_vals), "expected_count": len(expected), "gap_examples": sorted(list(missing))[:20]})
                sample_failures.append({"column": col, "message": f"Faltan {n_fail} valores secuenciales entre {sorted_vals[0]} y {sorted_vals[-1]}"})
        passed = failed == 0
        rec = None if passed else f"{failed} salto(s) en IDs secuenciales. Revisar eliminaciones o fallos en generación"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=min(failed, 1), failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class MissingFKCheck(Rule):
    name = "missing_fk_check"
    description = "Detecta IDs referenciados que no existen en la tabla padre (versión extendida de integridad referencial con soporte multi-columna)"

    def __init__(self, severity: str = "error", references: list[dict] | None = None):
        super().__init__(severity)
        self.references = references or []

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        if not self.references:
            # Auto-detect from column names: check columns ending in "_id"
            id_cols = [c for c in df.columns if c.lower().endswith("_id") and c.lower() != "id"]
            if id_cols:
                self.references = [{"fk_col": c, "pk_values": None} for c in id_cols]
            else:
                return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=[{"note": "Sin referencias configuradas. Usar references=[{fk_col: str, pk_values: set|None}]"}], recommendation=None)
        for ref in self.references:
            fk_col = ref.get("fk_col", "")
            if fk_col not in df.columns:
                continue
            pk_values = ref.get("pk_values")
            fk_vals = df[fk_col].dropna()
            if fk_vals.empty:
                continue
            total += len(fk_vals)
            if pk_values is not None:
                orphaned = ~fk_vals.isin(pk_values)
                n_fail = int(orphaned.sum())
                if n_fail:
                    failed += n_fail
                    details.append({"column": fk_col, "orphans": n_fail, "total": len(fk_vals), "pct": round(n_fail / len(fk_vals) * 100, 2)})
                    for idx in fk_vals[orphaned].index:
                        sample_failures.append({"column": fk_col, "row": int(idx), "value": str(fk_vals.loc[idx])})
        passed = failed == 0
        rec = None if passed else f"{failed} valores huérfanos en columnas FK. Verificar integridad referencial"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)
