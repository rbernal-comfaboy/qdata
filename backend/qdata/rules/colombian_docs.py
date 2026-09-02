"""Validación de documentos de identificación colombianos:
Cédula de Ciudadanía (cedula_valid) y NIT con dígito de verificación
(nit_valid, Módulo 11 DIAN)."""

import re

import pandas as pd

from qdata.rules.base import Rule, RuleResult
from qdata.rules.format_rules import _norm_phone_str, _row_values
from qdata.rules.person_fields import doc_dv_column, doc_number_column, doc_type_column, nit_columns

_CC_DIGITS_RE = re.compile(r"^\d+$")
_NON_ALNUM_RE = re.compile(r"[^0-9A-Za-z]")
_NIT_BAD_CHARS_RE = re.compile(r"[^0-9.,\-\s]")
_NIT_SEPARATORS_RE = re.compile(r"[\s.,]")
_NIT_DIGITS_RE = re.compile(r"\d+")

_CC_TYPE_NORMS = ("CC", "CEDULA", "CEDULACIUDADANIA", "CEDULADECIUDADANIA")
_NIT_TYPE_NORMS = ("NIT",)

# Pesos del Módulo 11 DIAN, aplicados de derecha a izquierda sobre el NIT
# rellenado con ceros a la izquierda hasta 15 dígitos (el dígito de la derecha
# se multiplica por el primer peso, 3).
_NIT_WEIGHTS = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def _norm_doc_type(v) -> str:
    s = str(v).strip().upper()
    return _NON_ALNUM_RE.sub("", s)


def _is_cc_type(v) -> bool:
    return _norm_doc_type(v) in _CC_TYPE_NORMS


def _is_nit_type(v) -> bool:
    return _norm_doc_type(v) in _NIT_TYPE_NORMS


def _nit_dv(base: str) -> int:
    """Dígito de verificación DIAN (Módulo 11) para un NIT sin DV."""
    digits = [int(ch) for ch in base]
    padded = [0] * (15 - len(digits)) + digits
    total = sum(d * _NIT_WEIGHTS[14 - i] for i, d in enumerate(padded))
    residuo = total % 11
    return residuo if residuo <= 1 else 11 - residuo


def _validate_nit(value: str, check_digit: bool, dv_column_value=None) -> dict:
    """Valida un valor de NIT. Devuelve un dict con reason (None = válido),
    expected/observed (para dv_incoherente), dv_present, warnings (lista
    informativa, sin fallo) y clasificacion.

    La base se sanitiza quitando ceros a la izquierda antes de validar
    (regla de negocio: no rechazar por ceros, solo avisar). Longitud de la
    base: 6-10 dígitos válida; 11 dígitos se acepta pero se avisa
    (asignaciones excepcionales de la DIAN); más de 11 falla.

    dv_column_value: valor de la columna de dígito de verificación (p.ej.
    perDigitoVerificacion). Cuando existe, es la fuente autoritativa del DV
    (tiene prioridad sobre el DV inline con guion)."""
    v = value.strip()
    result = {"reason": None, "expected": None, "observed": None, "dv_present": False, "warnings": [], "clasificacion": None}

    if not v:
        result["reason"] = "vacio"
        return result

    if _NIT_BAD_CHARS_RE.search(v):
        result["reason"] = "caracteres_invalidos"
        return result

    dv_from_col = None
    if dv_column_value is not None and not _is_na(dv_column_value):
        s = _norm_phone_str(str(dv_column_value)).strip()
        if s:
            dv_from_col = s

    base = v
    inline_dv = None
    if "-" in v:
        base, _, dv_part = v.rpartition("-")
        dv_part = _NIT_SEPARATORS_RE.sub("", dv_part)
        if not _NIT_DIGITS_RE.fullmatch(dv_part) or len(dv_part) != 1:
            result["reason"] = "formato_dv_invalido"
            return result
        inline_dv = dv_part

    base = _NIT_SEPARATORS_RE.sub("", base)
    if not _NIT_DIGITS_RE.fullmatch(base):
        result["reason"] = "caracteres_invalidos"
        return result

    if base.startswith("0"):
        result["warnings"].append("ceros_a_la_izquierda")
    base = base.lstrip("0")
    if not base:
        result["reason"] = "longitud_invalida"
        return result
    if len(base) < 6:
        result["reason"] = "longitud_invalida"
        return result
    if len(base) > 11:
        result["reason"] = "mas_de_11_digitos"
        return result
    if len(base) == 11:
        result["warnings"].append("longitud_elevada")

    result["clasificacion"] = "juridica" if base[0] in ("8", "9") else "natural"

    dv = dv_from_col or inline_dv
    if dv and check_digit:
        result["dv_present"] = True
        result["observed"] = dv
        expected = _nit_dv(base)
        result["expected"] = str(expected)
        if expected != int(dv):
            result["reason"] = "dv_incoherente"
    return result


def _is_na(v) -> bool:
    import math
    if v is None:
        return True
    try:
        if isinstance(v, float) and math.isnan(v):
            return True
    except Exception:
        pass
    try:
        if v != v:  # NaN
            return True
    except Exception:
        pass
    return False


class CedulaCheck(Rule):
    name = "cedula_valid"
    description = "Valida formato de Cédula de Ciudadanía colombiana (CC)"

    def __init__(self, severity: str = "error", columns: list | None = None):
        super().__init__(severity)
        self.columns = columns

    @staticmethod
    def _classify(value: str) -> str | None:
        length = len(value)
        if length in (6, 7):
            return "ancestros"
        if length == 8:
            return "contemporaneo"
        if length == 10 and value.startswith("1"):
            return "jovenes_nuip"
        return None

    @staticmethod
    def _validate(value: str) -> str | None:
        if not _CC_DIGITS_RE.match(value):
            return "letras_o_caracteres_no_numericos"
        length = len(value)
        if length not in (6, 7, 8, 10):
            return "longitud_invalida"
        if length == 10 and not value.startswith("1"):
            return "nuip_debe_iniciar_en_1"
        return None

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        details = []
        sample_failures = []
        doc_num_col = self.columns[0] if self.columns else doc_number_column(df.columns)
        if doc_num_col is None or doc_num_col not in df.columns:
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=details, sample_failures=sample_failures, recommendation=None)

        mask = pd.Series(True, index=df.index)
        doc_type_col = doc_type_column(df.columns)
        if doc_type_col and doc_type_col in df.columns:
            type_series = df[doc_type_col].dropna().astype(str)
            is_cc = type_series.apply(_is_cc_type)
            if is_cc.any():
                mask = is_cc

        series = df.loc[mask, doc_num_col].dropna()
        total = int(len(series))
        if total == 0:
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=details, sample_failures=sample_failures, recommendation=None)

        vals = series.astype(str).map(lambda s: _norm_phone_str(s).strip())
        reasons = vals.map(self._validate)
        failed_mask = reasons.notna()
        n_fail = int(failed_mask.sum())

        cls = vals.map(self._classify)
        clasificacion = {k: int(((~failed_mask) & (cls == k)).sum()) for k in ("ancestros", "contemporaneo", "jovenes_nuip")}
        clasificacion = {k: v for k, v in clasificacion.items() if v}

        if n_fail:
            reason_counts = {k: int(v) for k, v in reasons[failed_mask].value_counts().items()}
            details.append({
                "column": doc_num_col,
                "failed": n_fail,
                "total": total,
                "pct": round(n_fail / total * 100, 2),
                "reason_counts": reason_counts,
                "clasificacion": clasificacion,
            })
            for idx in series[failed_mask].index:
                sample_failures.append({
                    "column": doc_num_col,
                    "row": int(idx),
                    "value": vals.loc[idx],
                    "reason": reasons.loc[idx],
                    "values": _row_values(df, idx),
                })

        passed = n_fail == 0
        rec = None if passed else "Verificar el número de cédula: solo dígitos con 6, 7, 8 o 10 posiciones (NUIP de 10 dígitos inicia en 1)"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=n_fail, failure_pct=round(n_fail / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class NitCheck(Rule):
    name = "nit_valid"
    description = "Valida formato de NIT colombiano y dígito de verificación (Módulo 11 DIAN)"

    def __init__(self, severity: str = "error", check_digit: bool = True, columns: list | None = None):
        super().__init__(severity)
        self.check_digit = bool(check_digit)
        self.columns = columns

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        details = []
        sample_failures = []

        if self.columns:
            nit_col = self.columns[0]
            scope = "explicit"
            mask = pd.Series(True, index=df.index)
        else:
            nit_cols = nit_columns(df.columns)
            if nit_cols:
                nit_col = nit_cols[0]
                scope = "nit_column"
                mask = pd.Series(True, index=df.index)
            else:
                nit_col = doc_number_column(df.columns)
                if nit_col is None or nit_col not in df.columns:
                    return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=details, sample_failures=sample_failures, recommendation=None)
                scope = "doc_number"
                mask = pd.Series(True, index=df.index)
                doc_type_col = doc_type_column(df.columns)
                if doc_type_col and doc_type_col in df.columns:
                    type_series = df[doc_type_col].dropna().astype(str)
                    is_nit = type_series.apply(_is_nit_type)
                    if is_nit.any():
                        mask = is_nit
                    else:
                        # Hay columna de tipo de documento pero ningún valor NIT:
                        # no se puede distinguir qué filas son NIT → no validar.
                        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=details, sample_failures=sample_failures, recommendation=None)

        if nit_col not in df.columns:
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=details, sample_failures=sample_failures, recommendation=None)

        dv_col = doc_dv_column(df.columns) if self.check_digit else None
        if dv_col and dv_col not in df.columns:
            dv_col = None

        series = df.loc[mask, nit_col].dropna()
        total = int(len(series))
        if total == 0:
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=details, sample_failures=sample_failures, recommendation=None)

        vals = series.astype(str).map(lambda s: _norm_phone_str(s).strip())
        dv_vals = None
        if dv_col:
            dv_series = df.loc[mask, dv_col]
            dv_vals = dv_series.loc[series.index]
        parsed = vals.index.map(lambda i: _validate_nit(vals.loc[i], self.check_digit, dv_vals.loc[i] if dv_vals is not None else None))
        parsed = pd.Series(list(parsed), index=vals.index)
        reasons = parsed.map(lambda r: r["reason"])
        failed_mask = reasons.notna()
        n_fail = int(failed_mask.sum())

        dvs_present = int(parsed.map(lambda r: r["dv_present"]).sum())
        dvs_checked = int(parsed.map(lambda r: r["dv_present"] and self.check_digit).sum())
        clasificacion = {k: int(parsed.map(lambda r: r["clasificacion"]).eq(k).sum()) for k in ("juridica", "natural")}
        clasificacion = {k: v for k, v in clasificacion.items() if v}

        warned_mask = parsed.map(lambda r: bool(r.get("warnings")))
        warning_counts = {}
        if warned_mask.any():
            for w in ("ceros_a_la_izquierda", "longitud_elevada"):
                n_w = int(parsed[warned_mask].map(lambda r: w in r["warnings"]).sum())
                if n_w:
                    warning_counts[w] = n_w

        if n_fail or warning_counts:
            detail = {
                "column": nit_col,
                "dv_column": dv_col,
                "failed": n_fail,
                "total": total,
                "pct": round(n_fail / total * 100, 2),
                "check_digit": self.check_digit,
                "dvs_present": dvs_present,
                "dvs_checked": dvs_checked,
                "clasificacion": clasificacion,
                "scope": scope,
            }
            if n_fail:
                detail["reason_counts"] = {k: int(v) for k, v in reasons[failed_mask].value_counts().items()}
            if warning_counts:
                detail["warning_counts"] = warning_counts
                warnings_sample = []
                for idx in series[warned_mask].index:
                    r = parsed.loc[idx]
                    warnings_sample.append(f"fila {idx}: '{vals.loc[idx]}' ({', '.join(r['warnings'])})")
                    if len(warnings_sample) >= 50:
                        break
                detail["warnings_sample"] = warnings_sample
            details.append(detail)
            for idx in series[failed_mask].index:
                r = parsed.loc[idx]
                entry = {
                    "column": nit_col,
                    "row": int(idx),
                    "value": vals.loc[idx],
                    "reason": r["reason"],
                    "values": _row_values(df, idx),
                }
                if r.get("warnings"):
                    entry["warning"] = r["warnings"]
                if r.get("expected") is not None:
                    entry["expected"] = r["expected"]
                if r.get("observed") is not None:
                    entry["observed"] = r["observed"]
                sample_failures.append(entry)

        passed = n_fail == 0
        rec = None if passed else "Verificar el NIT contra el certificado de la DIAN: la base debe ser numérica de 6 a 10 dígitos (11 solo en asignaciones excepcionales) sin ceros a la izquierda, y el dígito de verificación debe coincidir con el Módulo 11. La certeza total de existencia y estado exige contrastar contra el RUT/RUES."
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=n_fail, failure_pct=round(n_fail / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)
