"""Reglas de validación de fechas: inválidas, rango temporal, inconsistencia entre fechas, freshness, latencia."""

from datetime import datetime, timezone, date
import pandas as pd
from qdata.rules.base import Rule, RuleResult


def _detect_date_cols(df: pd.DataFrame) -> list[str]:
    cols = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            cols.append(col)
        elif pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            try:
                parsed = pd.to_datetime(df[col].dropna().astype(str), errors="coerce")
                if parsed.notna().sum() >= max(3, len(df) * 0.5):
                    cols.append(col)
            except (ValueError, TypeError):
                pass
    return cols


def _parse_dates(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    return pd.to_datetime(series, errors="coerce")


class InvalidDateCheck(Rule):
    name = "invalid_date_check"
    description = "Detecta fechas imposibles: 30 febrero, año negativo, mes >12, día >31"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        for col in _detect_date_cols(df):
            raw = df[col].dropna()
            if len(raw) < 2:
                continue
            str_vals = raw.astype(str)
            parsed = pd.to_datetime(str_vals, errors="coerce")
            total += len(raw)
            n_fail = int(parsed.isna().sum())
            if n_fail:
                failed += n_fail
                invalid_mask = parsed.isna()
                details.append({"column": col, "failed": n_fail, "total": len(raw), "pct": round(n_fail / len(raw) * 100, 2)})
                for idx in raw[invalid_mask].index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(raw.loc[idx])})
        passed = failed == 0
        rec = None if passed else "Corregir fechas mal formadas. Usar formato ISO 8601 (YYYY-MM-DD)"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class DateRangeCheck(Rule):
    name = "date_range_check"
    description = "Detecta fechas fuera de época: nacimientos <1900 o >hoy, fechas futuras en campos históricos"

    def __init__(self, severity: str = "error", min_year: int = 1900, max_date: str | None = None):
        super().__init__(severity)
        self.min_year = min_year
        self.max_date = pd.Timestamp(max_date) if max_date else pd.Timestamp.now()

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        for col in _detect_date_cols(df):
            series = _parse_dates(df[col].dropna())
            total += len(series)
            too_early = series < pd.Timestamp(f"{self.min_year}-01-01")
            too_late = series > self.max_date
            comb = too_early | too_late
            n_fail = int(comb.sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(series), "pct": round(n_fail / len(series) * 100, 2), "before_min": int(too_early.sum()), "after_max": int(too_late.sum())})
                for idx in comb[comb].index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(series.loc[idx])})
        passed = failed == 0
        rec = None if passed else f"Revisar fechas fuera del rango [{self.min_year}, {self.max_date.date()}]"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class DateInconsistencyCheck(Rule):
    name = "date_inconsistency_check"
    description = "Detecta relaciones temporales ilógicas entre pares de columnas fecha"

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        total = 0; failed = 0; details = []; sample_failures = []
        date_cols = _detect_date_cols(df)
        for i in range(len(date_cols)):
            for j in range(i + 1, len(date_cols)):
                c1, c2 = date_cols[i], date_cols[j]
                s1 = _parse_dates(df[c1])
                s2 = _parse_dates(df[c2])
                valid = s1.notna() & s2.notna()
                n_valid = int(valid.sum())
                if n_valid < 2:
                    continue
                total += n_valid
                # flag if c1 > c2 in >50% of cases (suggesting c1 should precede c2)
                gt = (s1 > s2) & valid
                lt = (s1 < s2) & valid
                if gt.sum() > n_valid * 0.5:
                    n_fail = int(gt.sum())
                    failed += n_fail
                    details.append({"column_pair": f"{c1} > {c2}", "failed": n_fail, "total": n_valid, "pct": round(n_fail / n_valid * 100, 2)})
                    for idx in gt[gt].index:
                        sample_failures.append({"row": int(idx), "col1": c1, "val1": str(s1.loc[idx]), "col2": c2, "val2": str(s2.loc[idx])})
        passed = failed == 0
        rec = None if passed else "Revisar pares de fechas inconsistentes. Verificar que fechas_initio <= fechas_fin"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total, failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class FreshnessCheck(Rule):
    name = "freshness_check"
    description = "Verifica que los datos estén dentro de una ventana temporal esperada"

    def __init__(self, severity: str = "warning", max_days_old: int = 365):
        super().__init__(severity)
        self.max_days_old = max_days_old

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        now = pd.Timestamp.now()
        cutoff = now - pd.Timedelta(days=self.max_days_old)
        total = 0; failed = 0; details = []; sample_failures = []
        for col in _detect_date_cols(df):
            series = _parse_dates(df[col].dropna())
            total += len(series)
            old = series < cutoff
            n_fail = int(old.sum())
            if n_fail:
                failed += n_fail
                details.append({"column": col, "failed": n_fail, "total": len(series), "pct": round(n_fail / len(series) * 100, 2), "oldest": str(series.min()), "newest": str(series.max())})
                for idx in old[old].index:
                    sample_failures.append({"column": col, "row": int(idx), "value": str(series.loc[idx])})
        passed = failed == 0
        rec = None if passed else f"Datos anteriores a {self.max_days_old} días. Verificar frescura de la fuente"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=total or len(df.columns), failed=failed, failure_pct=round(failed / (total or 1) * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)


class LatencyCheck(Rule):
    name = "latency_check"
    description = "Mide la latencia entre timestamps de evento e ingesta"

    def __init__(self, severity: str = "warning", max_latency_hours: float = 24, event_col: str = "event_timestamp", ingest_col: str = "ingested_at"):
        super().__init__(severity)
        self.max_latency_hours = max_latency_hours
        self.event_col = event_col
        self.ingest_col = ingest_col

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        if self.event_col not in df.columns or self.ingest_col not in df.columns:
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=[{"note": f"Columnas '{self.event_col}' y/o '{self.ingest_col}' no encontradas"}], recommendation=None)
        event = _parse_dates(df[self.event_col])
        ingest = _parse_dates(df[self.ingest_col])
        valid = event.notna() & ingest.notna()
        n_valid = int(valid.sum())
        if n_valid == 0:
            return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=True, total=0, failed=0, failure_pct=0, details=[{"note": "Sin pares fecha válidos para medir latencia"}], recommendation=None)
        latency_h = ((ingest - event).dt.total_seconds() / 3600).abs()
        high_latency = latency_h > self.max_latency_hours
        n_fail = int(high_latency.sum())
        details = [{"event_col": self.event_col, "ingest_col": self.ingest_col, "failed": n_fail, "total": n_valid, "pct": round(n_fail / n_valid * 100, 2), "max_latency_h": round(float(latency_h.max()), 2), "avg_latency_h": round(float(latency_h.mean()), 2)}]
        sample_failures = []
        if n_fail:
            for idx in high_latency[high_latency].index:
                sample_failures.append({"row": int(idx), "event": str(event.loc[idx]), "ingest": str(ingest.loc[idx]), "latency_h": round(float(latency_h.loc[idx]), 2)})
        passed = n_fail == 0
        rec = None if passed else f"Latencia promedio de {details[0]['avg_latency_h']:.1f}h. Revisar pipeline de ingesta"
        return RuleResult(rule_name=self.name, description=self.description, severity=self.severity, passed=passed, total=n_valid, failed=n_fail, failure_pct=round(n_fail / n_valid * 100, 2), details=details, sample_failures=sample_failures, recommendation=rec)
