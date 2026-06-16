"""Reglas de validación de formato: email, caracteres especiales, longitud, trim, mayúsculas, teléfono, CP, RFC/CURP."""

import re
import pandas as pd
from qdata.rules.base import Rule, RuleResult


def _str_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c])]


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$")
PHONE_MX = re.compile(r"^(\+52)?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$")
PHONE_US = re.compile(r"^\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$")
PHONE_INTL = re.compile(r"^\+[\d]{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,9}$")
ZIP_MX = re.compile(r"^\d{5}$")
ZIP_US = re.compile(r"^\d{5}(-\d{4})?$")
ZIP_UK = re.compile(r"^[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}$", re.IGNORECASE)
RFC_MX = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9][A-Z0-9]?[0-9A-Z]$")
CURP_MX = re.compile(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[0-9A-Z]\d$")


class EmailCheck(Rule):
    name = "email_check"
    description = "Valida formato de correo electrónico según RFC 5322"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        for col in _str_cols(df):
            series = df[col].dropna().astype(str)
            candidates = series[series.str.contains("@", na=False)]
            if len(candidates) < 2:
                continue
            total += len(candidates)
            mask = candidates.str.match(EMAIL_REGEX)
            n_fail = int((~mask).sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(candidates), "pct": round(n_fail / len(candidates) * 100, 2)})
                for idx in candidates[~mask].head(5).index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(candidates.loc[idx])})
        passed = failed == 0
        rec = None if passed else "Corregir direcciones de email inválidas. Verificar dominios y formato local@dominio.tld"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total or len(df.columns), failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class SpecialCharsCheck(Rule):
    name = "special_chars_check"
    description = "Detecta caracteres especiales no imprimibles, de control o no esperados en campos de texto"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        control_re = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
        zero_width = re.compile(r"[\u200B\u200C\u200D\uFEFF]")
        for col in _str_cols(df):
            series = df[col].dropna().astype(str)
            total += len(series)
            bad_ctrl = series.str.contains(control_re, na=False)
            bad_zw = series.str.contains(zero_width, na=False)
            comb = bad_ctrl | bad_zw
            n_fail = int(comb.sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(series), "pct": round(n_fail / len(series) * 100, 2), "types": list(set(["control" if bad_ctrl.iloc[i] else "zero_width" for i in comb[comb].index]))})
                for idx in comb[comb].head(5).index:
                    sample_failures.append({"column": col, "row": int(idx), "value": repr(series.loc[idx])})
        passed = failed == 0
        rec = None if passed else "Limpiar caracteres de control y zero-width. Usar limpieza Unicode NFKC"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class StringLengthCheck(Rule):
    name = "string_length_check"
    description = "Verifica que la longitud de cadenas esté dentro de rangos esperados"

    def __init__(self, severity: str = "error", min_length: int = 1, max_length: int = 255):
        super().__init__(severity)
        self.min_length = min_length
        self.max_length = max_length

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        for col in _str_cols(df):
            series = df[col].dropna().astype(str)
            total += len(series)
            too_short = series.str.len() < self.min_length
            too_long = series.str.len() > self.max_length
            comb = too_short | too_long
            n_fail = int(comb.sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(series), "pct": round(n_fail / len(series) * 100, 2), "min_len": int(series.str.len().min()), "max_len": int(series.str.len().max())})
                for idx in comb[comb].head(5).index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(series.loc[idx])[:50], "length": len(str(series.loc[idx]))})
        passed = failed == 0
        rec = None if passed else f"Ajustar longitudes de cadena al rango esperado [{self.min_length}, {self.max_length}]"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class TrimCheck(Rule):
    name = "trim_check"
    description = "Detecta espacios leading/trailing en campos de texto"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        for col in _str_cols(df):
            series = df[col].dropna().astype(str)
            total += len(series)
            has_lead = series.str.startswith(" ", na=False)
            has_trail = series.str.endswith(" ", na=False)
            comb = has_lead | has_trail
            n_fail = int(comb.sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(series), "pct": round(n_fail / len(series) * 100, 2), "leading": int(has_lead.sum()), "trailing": int(has_trail.sum())})
                for idx in comb[comb].head(5).index:
                    val = str(series.loc[idx])
                    sample_failures.append({"column": col, "row": int(idx), "value": repr(val)})
        passed = failed == 0
        rec = None if passed else "Aplicar .str.strip() a las columnas afectadas para eliminar espacios extras"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class CaseConsistencyCheck(Rule):
    name = "case_consistency_check"
    description = "Detecta mezcla inconsistente de mayúsculas/minúsculas en campos que deberían ser uniformes"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        for col in _str_cols(df):
            series = df[col].dropna().astype(str)
            if len(series) < 5:
                continue
            lower = series.str.islower().sum()
            upper = series.str.isupper().sum()
            total_clean = len(series) - (series.str.match(r"^[\d\s]+$", na=False).sum())
            if total_clean < 3:
                continue
            total += total_clean
            # If >80% are lowercase, flag non-lowercase; if >80% uppercase, flag non-uppercase
            if lower / total_clean > 0.8:
                mask = ~series.str.islower()
            elif upper / total_clean > 0.8:
                mask = ~series.str.isupper()
            else:
                mask = pd.Series([False] * len(series))
            n_fail = int(mask.sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": total_clean, "pct": round(n_fail / total_clean * 100, 2), "dominant_case": "lower" if lower > upper else "upper"})
                for idx in mask[mask].head(5).index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(series.loc[idx])})
        passed = failed == 0
        rec = None if passed else "Uniformar mayúsculas/minúsculas según el estándar del campo (.lower() o .upper())"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class PhoneCheck(Rule):
    name = "phone_check"
    description = "Valida formato de números telefónicos (MX, US, internacional)"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        phone_re = re.compile(r"[\d\s\-\(\)\+\.]{7,}")
        for col in _str_cols(df):
            series = df[col].dropna().astype(str)
            candidates = series[series.str.contains(phone_re, na=False)]
            if len(candidates) < 2:
                continue
            total += len(candidates)
            valid = candidates.apply(lambda v: bool(PHONE_MX.match(v) or PHONE_US.match(v) or PHONE_INTL.match(v)))
            n_fail = int((~valid).sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(candidates), "pct": round(n_fail / len(candidates) * 100, 2)})
                for idx in candidates[~valid].head(5).index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(candidates.loc[idx])})
        passed = failed == 0
        rec = None if passed else "Estandarizar formato telefónico a +52 (MX) o +1 (US) con 10 dígitos"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total or len(df.columns), failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class ZipCodeCheck(Rule):
    name = "zip_code_check"
    description = "Valida formato de código postal (MX, US, UK)"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        digit_re = re.compile(r"\d{4,}")
        for col in _str_cols(df):
            series = df[col].dropna().astype(str).str.strip()
            candidates = series[series.str.contains(digit_re, na=False)]
            if len(candidates) < 2:
                continue
            total += len(candidates)
            valid = candidates.apply(lambda v: bool(ZIP_MX.match(v) or ZIP_US.match(v) or ZIP_UK.match(v)))
            n_fail = int((~valid).sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(candidates), "pct": round(n_fail / len(candidates) * 100, 2)})
                for idx in candidates[~valid].head(5).index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(candidates.loc[idx])})
        passed = failed == 0
        rec = None if passed else "Estandarizar códigos postales: MX=5 dígitos, US=5 o 9 dígitos, UK=formato alfanumérico"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total or len(df.columns), failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class RfcCurpCheck(Rule):
    name = "rfc_curp_check"
    description = "Valida estructura de RFC y CURP mexicanos"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        for col in _str_cols(df):
            series = df[col].dropna().astype(str).str.upper().str.strip()
            candidates = series[series.str.len() >= 10]
            if len(candidates) < 2:
                continue
            total += len(candidates)
            is_rfc = candidates.apply(lambda v: bool(RFC_MX.match(v)))
            is_curp = candidates.apply(lambda v: bool(CURP_MX.match(v)))
            valid = is_rfc | is_curp
            n_fail = int((~valid).sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(candidates), "pct": round(n_fail / len(candidates) * 100, 2), "rfc_found": int(is_rfc.sum()), "curp_found": int(is_curp.sum())})
                for idx in candidates[~valid].head(5).index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(candidates.loc[idx])})
        passed = failed == 0
        rec = None if passed else "Corregir RFC (13 chars) o CURP (18 chars) según formato oficial SAT"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total or len(df.columns), failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)
