"""Reglas de validación de negocio: consistencia cruzada, dependencias funcionales, balance de clases, sesgo booleano, columnas derivadas."""

import pandas as pd
import numpy as np
from qdata.rules.base import Rule, RuleResult


def _row_values(df: pd.DataFrame, idx: int) -> dict:
    row = df.loc[idx]
    return {col: (v.item() if hasattr(v, 'item') else v) for col, v in row.items()}


class CrossConsistencyCheck(Rule):
    name = "cross_consistency_check"
    description = "Valida relaciones aritméticas y lógicas entre columnas (total = precio × cantidad, edad = año_actual - año_nacimiento)"

    def __init__(self, severity: str = "error", rules: list[dict] | None = None):
        super().__init__(severity)
        self.rules = rules or []

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        now = pd.Timestamp.now().year
        # Auto-detect common patterns
        auto_rules = []
        cols_lower = {c.lower(): c for c in df.columns}
        if "total" in cols_lower and "precio" in cols_lower and "cantidad" in cols_lower:
            auto_rules.append(("total = precio × cantidad", lambda r: abs(r[cols_lower["total"]] - (r[cols_lower["precio"]] * r[cols_lower["cantidad"]])) < 0.01))
        if "subtotal" in cols_lower and "total" in cols_lower:
            auto_rules.append(("subtotal ≤ total", lambda r: r[cols_lower["subtotal"]] <= r[cols_lower["total"]] + 0.01))
        if "edad" in cols_lower and any(k in cols_lower for k in ("fecha_nacimiento", "fecha_nac", "nacimiento", "birth_date", "birth")):
            birth_col = next(cols_lower[k] for k in ("fecha_nacimiento", "fecha_nac", "nacimiento", "birth_date", "birth") if k in cols_lower)
            auto_rules.append(("edad ≈ año_actual - año_nacimiento", lambda r: True))  # skip complex check
        seen_pairs = set()
        for label, check_fn in auto_rules + [(r.get("label", "custom"), eval(f"lambda r: {r['expr']}")) for r in self.rules if "expr" in r]:
            pair_key = label.split("=")[0].strip()
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            result = df.apply(check_fn, axis=1)
            total += len(result)
            n_fail = int((~result).sum())
            if n_fail:
                failed += n_fail
                details.append({"rule": label, "failed": n_fail, "total": len(result), "pct": round(n_fail / len(result) * 100, 2)})
                for idx in result[~result].index:
                    sample_failures.append({"row": int(idx), "rule": label, "values": _row_values(df, idx)})
        passed = failed == 0
        rec = None if passed else "Revisar violaciones de consistencia cruzada. Verificar cálculos y relaciones entre columnas"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total or len(df.columns), failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class FunctionalDependencyCheck(Rule):
    name = "functional_dependency_check"
    description = "Detecta violaciones de dependencias funcionales (mismo código_postal → distinto municipio)"

    def __init__(self, severity: str = "error", fd_pairs: list[tuple[str, str]] | None = None):
        super().__init__(severity)
        self.fd_pairs = fd_pairs or []

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        # Auto-detect: find columns with same cardinality or name hints
        auto_pairs = []
        name_map = {c.lower(): c for c in df.columns}
        fd_hints = [
            ("codigo_postal", "municipio"), ("zip", "city"), ("zip_code", "city"),
            ("id_empleado", "nombre"), ("employee_id", "name"), ("id_cliente", "cliente"),
            ("sku", "producto"), ("product_code", "product_name"),
            ("id_depto", "departamento"), ("dept_id", "department_name"),
        ]
        for det, dep in fd_hints:
            if det in name_map and dep in name_map:
                auto_pairs.append((name_map[det], name_map[dep]))
        for det_col, dep_col in auto_pairs + self.fd_pairs:
            if det_col not in df.columns or dep_col not in df.columns:
                continue
            grouped = df.groupby(det_col)[dep_col].nunique()
            violations = grouped[grouped > 1]
            total += len(grouped)
            n_fail = len(violations)
            if n_fail:
                failed += n_fail
                details.append({"determinant": det_col, "dependent": dep_col, "failed": n_fail, "total": len(grouped), "pct": round(n_fail / len(grouped) * 100, 2)})
                for det_val in violations.index:
                    rows = df[df[det_col] == det_val][[det_col, dep_col]]
                    for _, r in rows.iterrows():
                        sample_failures.append({"determinant": det_col, "value": str(r[det_col]), "dependent": dep_col, "dep_values": str(r[dep_col]), "values": _row_values(df, r.name)})
        passed = failed == 0
        rec = None if passed else "Corregir violaciones de dependencia funcional. Un valor del determinante debe corresponder a un único valor del dependiente"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class ClassBalanceCheck(Rule):
    name = "class_balance_check"
    description = "Detecta desbalance extremo en columnas categóricas (>98% un solo valor)"

    def __init__(self, severity: str = "warning", threshold: float = 0.98):
        super().__init__(severity)
        self.threshold = threshold

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        str_candidate_cols = [c for c in df.columns if pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c]) or pd.api.types.is_categorical_dtype(df[c])]
        for col in str_candidate_cols:
            series = df[col].dropna()
            if len(series) < 5:
                continue
            vc = series.value_counts(normalize=True)
            top_pct = vc.iloc[0]
            total += 1
            if top_pct >= self.threshold:
                failed += 1
                details.append({"column": col, "top_value": str(vc.index[0]), "top_pct": round(top_pct * 100, 2), "unique_values": len(vc)})
        for col in df.select_dtypes(include=["number"]).columns:
            series = df[col].dropna()
            if len(series) < 5 or series.nunique() > 10:
                continue
            vc = series.value_counts(normalize=True)
            top_pct = vc.iloc[0]
            total += 1
            if top_pct >= self.threshold:
                failed += 1
                details.append({"column": col, "top_value": str(vc.index[0]), "top_pct": round(top_pct * 100, 2), "unique_values": len(vc)})
        passed = failed == 0
        rec = None if passed else f"Columnas con >{self.threshold*100:.0f}% de un mismo valor. Evaluar si aportan información"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class BooleanBiasCheck(Rule):
    name = "boolean_bias_check"
    description = "Detecta columnas booleanas extremadamente sesgadas (>99% True o >99% False)"

    def __init__(self, severity: str = "warning", threshold: float = 0.99):
        super().__init__(severity)
        self.threshold = threshold

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        for col in df.columns:
            if df[col].dropna().nunique() > 2:
                continue
            nunique = df[col].dropna().nunique()
            if nunique == 0:
                continue
            series = df[col].dropna().astype(str).str.lower().map({"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False, "si": True, "s": True, "n": False, "t": True, "f": False})
            bools = series.dropna()
            if len(bools) < 5:
                continue
            total += 1
            true_pct = bools.sum() / len(bools)
            if true_pct >= self.threshold:
                failed += 1
                details.append({"column": col, "bias": "True", "true_pct": round(true_pct * 100, 2), "total_rows": len(bools)})
            elif true_pct <= 1 - self.threshold:
                failed += 1
                details.append({"column": col, "bias": "False", "false_pct": round((1 - true_pct) * 100, 2), "total_rows": len(bools)})
        passed = failed == 0
        rec = None if passed else f"Columnas booleanas con sesgo >{self.threshold*100:.0f}%. Considerar si son realmente útiles"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class DerivedColumnCheck(Rule):
    name = "derived_column_check"
    description = "Verifica que columnas calculadas coincidan con su fórmula esperada"

    def __init__(self, severity: str = "error", derivations: list[dict] | None = None):
        super().__init__(severity)
        self.derivations = derivations or []

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        cols_lower = {c.lower(): c for c in df.columns}
        auto_derivations = []
        if "edad" in cols_lower:
            for bcol in ("fecha_nacimiento", "fecha_nac", "nacimiento", "birth_date", "birth", "birthdate"):
                if bcol in cols_lower:
                    auto_derivations.append(("edad", cols_lower[bcol], lambda df: pd.Timestamp.now().year - pd.to_datetime(df[bcol], errors="coerce").dt.year))
                    break
        if "iva" in cols_lower and "subtotal" in cols_lower:
            auto_derivations.append(("iva", "subtotal", lambda df: df["subtotal"] * 0.16))
        if "total" in cols_lower and "subtotal" in cols_lower and "iva" in cols_lower:
            auto_derivations.append(("total", ["subtotal", "iva"], lambda df: df["subtotal"] + df["iva"]))
        for derivation in auto_derivations + [(r["target"], r.get("source", ""), eval(f"lambda df: {r['formula']}")) for r in self.derivations if "formula" in r]:
            target_col = derivation[0] if isinstance(derivation[0], str) else derivation[0]
            if target_col not in df.columns:
                continue
            expected = derivation[2](df)
            actual = pd.to_numeric(df[target_col], errors="coerce")
            valid = expected.notna() & actual.notna() & (expected != 0)
            n_valid = int(valid.sum())
            if n_valid < 2:
                continue
            total += n_valid
            diff_pct = ((actual - expected) / expected.abs()).abs() * 100
            mismatch = diff_pct > 1.0
            n_fail = int(mismatch.sum())
            if n_fail:
                failed += n_fail
                details.append({"column": target_col, "failed": n_fail, "total": n_valid, "pct": round(n_fail / n_valid * 100, 2), "max_deviation_pct": round(float(diff_pct[mismatch].max()), 2)})
                for idx in mismatch[mismatch].index:
                    sample_failures.append({"row": int(idx), "column": target_col, "actual": float(actual.loc[idx]), "expected": float(expected.loc[idx]), "diff_pct": round(float(diff_pct.loc[idx]), 2)})
        passed = failed == 0
        rec = None if passed else "Revisar columnas derivadas que no coinciden con su fórmula de cálculo"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)
