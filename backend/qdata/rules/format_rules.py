"""Reglas de validación de formato: email, caracteres especiales, longitud, trim, mayúsculas, teléfono, CP, RFC/CURP."""

import re
import numpy as np
import pandas as pd
from qdata.rules.base import Rule, RuleResult


def _str_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c])]


def _row_values(df: pd.DataFrame, idx: int) -> dict:
    row = df.loc[idx]
    return {col: (v.item() if hasattr(v, 'item') else v) for col, v in row.items()}


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$")
PHONE_MX = re.compile(r"^(\+52)?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$")
PHONE_US = re.compile(r"^\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$")
PHONE_CO = re.compile(r"^(?:\+?57)?\s*(?:3\d{9}|(?:1|2|4|5|6|8)\d{7,9})$")
PHONE_INTL = re.compile(r"^\+[\d]{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,9}$")
PHONE_COL_RE = re.compile(r"telef|celu|celular|mobile|phone|tel[^e]|fijo|contacto|whatsapp|movil", re.IGNORECASE)
PHONE_COL_EXCLUDE_RE = re.compile(r"nume|num|id|doc|docu|ident|cedula|cédula|rut|dni|codigo|código|usuario|user", re.IGNORECASE)
EMAIL_COL_RE = re.compile(r"email|correo|e-?mail|mail|contacto", re.IGNORECASE)
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
            is_email_col = bool(EMAIL_COL_RE.search(col))
            has_dot_after_at = candidates.str.contains(r"@.+\.", regex=True, na=False).any()
            has_email_signal = has_dot_after_at
            if not is_email_col and not has_email_signal:
                continue
            mask = candidates.str.match(EMAIL_REGEX)
            valid_ratio = mask.sum() / len(candidates)
            if mask.sum() == 0 or valid_ratio < 0.30:
                continue
            total += len(candidates)
            n_fail = int((~mask).sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(candidates), "pct": round(n_fail / len(candidates) * 100, 2)})
                for idx in candidates[~mask].index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(candidates.loc[idx]), "values": _row_values(df, idx)})
        passed = failed == 0
        rec = None if passed else "Corregir direcciones de email inválidas. Verificar dominios y formato local@dominio.tld"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total or len(df.columns), failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class SpecialCharsCheck(Rule):
    name = "special_chars_check"
    description = "Detecta caracteres especiales problemáticos: de control, zero-width, uso privado, seguridad y espacios no estándar"

    CHAR_CATEGORIES = {
        "critical": (re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]"), "Carácter de control crítico"),
        "zero_width": (re.compile(r"[\u200B\u200C\u200D\uFEFF]"), "Carácter de ancho cero"),
        "private_use": (re.compile(r"[\uE000-\uF8FF]"), "Carácter de uso privado"),
        "security": (re.compile(r"[\u202A-\u202E\u2066-\u2069]"), "Override de dirección (riesgo de seguridad)"),
        "nonstandard_space": (re.compile(r"[\u00A0\u2000-\u200A\u202F\u205F\u3000]"), "Espacio no estándar"),
    }

    SEVERITY_ORDER = {"critical": 0, "security": 1, "control": 2, "zero_width": 3, "private_use": 4, "nonstandard_space": 5}

    CATEGORY_LABELS = {
        "critical": "control_crítico",
        "zero_width": "ancho_cero",
        "private_use": "uso_privado",
        "security": "seguridad",
        "nonstandard_space": "espacio_no_estándar",
    }

    @staticmethod
    def _char_name(char: str) -> str:
        cp = ord(char)
        names = {
            0x00: "NULL", 0x01: "SOH", 0x02: "STX", 0x03: "ETX", 0x04: "EOT",
            0x05: "ENQ", 0x06: "ACK", 0x07: "BEL", 0x08: "BS", 0x09: "TAB",
            0x0A: "LF", 0x0B: "VT", 0x0C: "FF", 0x0D: "CR", 0x0E: "SO",
            0x0F: "SI", 0x10: "DLE", 0x11: "DC1", 0x12: "DC2", 0x13: "DC3",
            0x14: "DC4", 0x15: "NAK", 0x16: "SYN", 0x17: "ETB", 0x18: "CAN",
            0x19: "EM", 0x1A: "SUB", 0x1B: "ESC", 0x1C: "FS", 0x1D: "GS",
            0x1E: "RS", 0x1F: "US", 0x7F: "DEL",
            0x200B: "ZWSP", 0x200C: "ZWNJ", 0x200D: "ZWJ", 0xFEFF: "BOM",
            0x202A: "LRE", 0x202B: "RLE", 0x202C: "PDF", 0x202D: "LRO",
            0x202E: "RLO", 0x2066: "LRI", 0x2067: "RLI", 0x2068: "FSI",
            0x2069: "PDI",
            0x00A0: "NBSP", 0x2000: "EN QUAD", 0x2001: "EM QUAD",
            0x2002: "EN SPACE", 0x2003: "EM SPACE", 0x2004: "THREE-PER-EM SPACE",
            0x2005: "FOUR-PER-EM SPACE", 0x2006: "SIX-PER-EM SPACE",
            0x2007: "FIGURE SPACE", 0x2008: "PUNCTUATION SPACE",
            0x2009: "THIN SPACE", 0x200A: "HAIR SPACE", 0x202F: "NARROW NBSP",
            0x205F: "MEDIUM MATHEMATICAL SPACE", 0x3000: "IDEOGRAPHIC SPACE",
        }
        return names.get(cp, f"U+{cp:04X}")

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        columns = kwargs.get("columns")
        total = 0
        failed = 0
        details = []
        sample_failures = []
        worst_severity = None

        cols_to_check = _str_cols(df)
        if columns:
            cols_to_check = [c for c in cols_to_check if c in columns]

        for col in cols_to_check:
            series = df[col].dropna().astype(str)
            total += len(series)
            col_types = {}
            col_bad_mask = pd.Series(False, index=series.index)

            for cat_name, (regex, _desc) in self.CHAR_CATEGORIES.items():
                mask = series.str.contains(regex, na=False)
                n = int(mask.sum())
                if n:
                    col_types[cat_name] = n
                    col_bad_mask = col_bad_mask | mask

            n_fail = int(col_bad_mask.sum())
            if n_fail:
                failed += n_fail
                sorted_types = sorted(col_types.keys(), key=lambda k: self.SEVERITY_ORDER.get(k, 99))
                for t in sorted_types:
                    if worst_severity is None or self.SEVERITY_ORDER.get(t, 99) < self.SEVERITY_ORDER.get(worst_severity, 99):
                        worst_severity = t
                details.append({
                    "column": col,
                    "failed": n_fail,
                    "total": len(series),
                    "pct": round(n_fail / len(series) * 100, 2),
                    "types": col_types,
                    "type_labels": [self.CATEGORY_LABELS.get(t, t) for t in sorted_types],
                })
                for idx in col_bad_mask[col_bad_mask].index:
                    val = series.loc[idx]
                    found_chars = []
                    for char in val:
                        for cat_name, (regex, _desc) in self.CHAR_CATEGORIES.items():
                            if regex.search(char):
                                found_chars.append({"char": repr(char), "name": self._char_name(char), "category": self.CATEGORY_LABELS.get(cat_name, cat_name)})
                                break
                    sample_failures.append({"column": col, "row": int(idx), "value": val, "chars_found": found_chars, "values": _row_values(df, idx)})

        passed = failed == 0
        if worst_severity == "critical":
            final_severity = "error"
        elif worst_severity in ("security",):
            final_severity = "error"
        else:
            final_severity = self.severity

        rec = None
        if not passed:
            recs = []
            if any(d.get("types", {}).get("critical") for d in details):
                recs.append("Remover caracteres de control críticos (null bytes, etc.)")
            if any(d.get("types", {}).get("security") for d in details):
                recs.append("Revisar caracteres de override RTL/LTR (riesgo de seguridad)")
            if any(d.get("types", {}).get("zero_width") for d in details):
                recs.append("Limpiar caracteres zero-width con normalización Unicode NFKC")
            if any(d.get("types", {}).get("private_use") for d in details):
                recs.append("Verificar caracteres de uso privado (pueden ser datos corruptos)")
            if any(d.get("types", {}).get("nonstandard_space") for d in details):
                recs.append("Reemplazar espacios no estándar por espacio ASCII normal")
            rec = ". ".join(recs)

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=final_severity,
            passed=passed,
            total=total,
            failed=failed,
            failure_pct=round(failed / (total or 1) * 100, 2),
            details=details,
            sample_failures=sample_failures,
            recommendation=rec,
        )


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
                for idx in comb[comb].index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(series.loc[idx])[:50], "length": len(str(series.loc[idx])), "values": _row_values(df, idx)})
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
                for idx in comb[comb].index:
                    val = str(series.loc[idx])
                    sample_failures.append({"column": col, "row": int(idx), "value": repr(val), "values": _row_values(df, idx)})
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
                for idx in mask[mask].index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(series.loc[idx]), "values": _row_values(df, idx)})
        passed = failed == 0
        rec = None if passed else "Uniformar mayúsculas/minúsculas según el estándar del campo (.lower() o .upper())"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class PhoneCheck(Rule):
    name = "phone_check"
    description = "Valida formato de números telefónicos (Colombia, MX, US, internacional)"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        phone_re = re.compile(r"[\d\s\-\(\)\+\.]{7,}")
        for col in _str_cols(df):
            series = df[col].dropna().astype(str)
            candidates = series[series.str.contains(phone_re, na=False)]
            if len(candidates) < 2:
                continue
            is_phone_col = bool(PHONE_COL_RE.search(col))
            is_excluded_col = bool(PHONE_COL_EXCLUDE_RE.search(col))
            if is_excluded_col and not is_phone_col:
                continue
            has_plus = candidates.str.startswith("+").any()
            has_parens = candidates.str.contains(r"\(\d{2,4}\)", regex=True, na=False).any()
            has_spaces_digits = candidates.str.contains(r"\d{2,}[\s]\d{2,}", regex=True, na=False).any()
            has_phone_signal = has_plus or has_parens or has_spaces_digits
            if not is_phone_col and not has_phone_signal:
                continue
            valid = candidates.apply(lambda v: bool(PHONE_MX.match(v) or PHONE_US.match(v) or PHONE_CO.match(v) or PHONE_INTL.match(v)))
            valid_ratio = valid.sum() / len(candidates)
            if valid.sum() == 0 or valid_ratio < 0.30:
                continue
            total += len(candidates)
            n_fail = int((~valid).sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(candidates), "pct": round(n_fail / len(candidates) * 100, 2)})
                for idx in candidates[~valid].index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(candidates.loc[idx]), "values": _row_values(df, idx)})
        passed = failed == 0
        rec = None if passed else "Estandarizar formato telefónico internacional (+57 Colombia, +52 México, +1 US)"
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
            valid = candidates.apply(lambda v: bool(ZIP_MX.match(v) or ZIP_US.match(v) or ZIP_UK.match(v)))
            if valid.sum() == 0:
                continue
            total += len(candidates)
            n_fail = int((~valid).sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(candidates), "pct": round(n_fail / len(candidates) * 100, 2)})
                for idx in candidates[~valid].index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(candidates.loc[idx]), "values": _row_values(df, idx)})
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
            is_rfc = candidates.apply(lambda v: bool(RFC_MX.match(v)))
            is_curp = candidates.apply(lambda v: bool(CURP_MX.match(v)))
            valid = is_rfc | is_curp
            if valid.sum() == 0:
                continue
            total += len(candidates)
            n_fail = int((~valid).sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(candidates), "pct": round(n_fail / len(candidates) * 100, 2), "rfc_found": int(is_rfc.sum()), "curp_found": int(is_curp.sum())})
                for idx in candidates[~valid].index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(candidates.loc[idx]), "values": _row_values(df, idx)})
        passed = failed == 0
        rec = None if passed else "Corregir RFC (13 chars) o CURP (18 chars) según formato oficial SAT"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total or len(df.columns), failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)
