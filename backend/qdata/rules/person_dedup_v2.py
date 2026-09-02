import re
import time
from collections import defaultdict, deque

import pandas as pd

from qdata.rules.base import Rule, RuleResult
from qdata.rules.person_dedup_rules import (
    _MAX_BLOCK_SIZE,
    _date_similarity,
    _find_connected_components,
    _id_similarity,
    _levenshtein_ratio,
    _name_similarity,
    _normalize,
    _pairs_from_blocks,
    _text_similarity,
)

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


def _classify_column(col: str) -> str:
    low = col.lower().strip()
    if re.search(r"fecha.{0,12}nac|nacimiento|birth|date_of_birth|\bfnac\b|f_nac", low):
        return "dob"
    if re.search(r"telef|phone|celular|celu|movil|mobil|whatsapp|ntel|fijo|contacto|_tel\b|^tel\b", low):
        return "phone"
    if re.search(r"email|e-?mail|correo|mail", low):
        return "email"
    if re.search(r"cedula|c[.\s-]?c\b|identif|documento|nro.{0,4}doc|num.{0,4}doc|numdoc|nume|nide|nuid|nudoc|docterc|doterc|nit|rut|dni|pasaporte|passport|_id$|^id$|perid", low):
        return "id"
    if re.search(r"apellid|surname|last_name|apel|ape[1-2]", low):
        return "surname"
    if re.search(r"nombre|nomb|first_name|given_name|primer_nombre|segundo_nombre", low):
        return "name"
    return "generic"


def _phone_similarity(a: str, b: str) -> float:
    da = re.sub(r"[^0-9]", "", str(a))
    db = re.sub(r"[^0-9]", "", str(b))
    if not da and not db:
        return 1.0
    if not da or not db:
        return 0.0
    if len(da) >= 10 and len(db) >= 10:
        da, db = da[-10:], db[-10:]
    return _levenshtein_ratio(da, db)


def _name_block_key(raw: str) -> str:
    tokens = _normalize(raw).split()
    if not tokens:
        return "_"
    first = tokens[0][:1]
    second = tokens[1][:1] if len(tokens) > 1 else "_"
    return first + second


def _digits(v) -> str:
    return re.sub(r"[^0-9]", "", str(v))


def _default_field_weight(col_type: str) -> float:
    return {
        "id": 0.30,
        "name": 0.25,
        "surname": 0.20,
        "dob": 0.15,
        "phone": 0.10,
        "email": 0.10,
        "generic": 0.10,
    }.get(col_type, 0.10)


class SimilarPeopleCheckV2(Rule):
    name = "personas_similares_v2"
    description = (
        "Personas similares V2: compara las columnas que selecciones con pesos configurables "
        "para detectar la misma persona registrada dos veces con pequeñas diferencias "
        "(cédula con dígitos cambiados, mismo nombre, etc.)"
    )

    def __init__(
        self,
        severity: str = "warning",
        mode: str = "rapido",
        threshold: float | None = None,
        columns: list[str] | None = None,
        weights: dict[str, float] | None = None,
        window_days: int = 3,
    ):
        super().__init__(severity)
        self.mode = mode
        self.columns = columns
        self.weights = weights
        self.window_days = window_days
        if threshold is not None:
            self.threshold = threshold
        elif mode == "profundo":
            self.threshold = 0.70
        else:
            self.threshold = 0.80

    def _field_sim(self, col_type: str, a, b) -> float:
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        if col_type == "id":
            return _id_similarity(a, b)
        if col_type == "dob":
            return _date_similarity(a, b, self.window_days)
        if col_type == "phone":
            return _phone_similarity(a, b)
        if col_type == "email":
            return _text_similarity(a, b)
        return _name_similarity(a, b)

    def _block_keys(self, col_type: str, raw) -> list[str]:
        if col_type == "id":
            d = _digits(raw)
            keys = []
            if len(d) > 2:
                keys.append("id-p:" + d[: max(1, len(d) - 2)])
                keys.append("id-s:" + d[-max(1, len(d) - 2):])
            else:
                keys.append("id-x:" + (d or "_"))
            return keys
        if col_type == "dob":
            m = re.search(r"(\d{4})", str(raw))
            return [f"dob:{m.group(1)}" if m else "dob:_"]
        if col_type == "phone":
            d = _digits(raw)
            return [f"ph:{d[-6:]}" if len(d) >= 6 else ("ph:" + (d or "_"))]
        if col_type == "surname":
            k = _normalize(raw)[:1] if _normalize(raw) else "_"
            return [f"sur:{k}"]
        if col_type == "name":
            return [f"nam:{_name_block_key(raw)}"]
        if col_type == "email":
            k = _normalize(raw)[:1] if _normalize(raw) else "_"
            return [f"ema:{k}"]
        k = _normalize(raw)[:1] if _normalize(raw) else "_"
        return [f"gen:{k}"]

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        progress_callback = kwargs.get("progress_callback")
        log_callback = kwargs.get("log_callback")

        def _cb(processed: int, total_: int, msg: str, phase: str = "", extra: dict | None = None) -> None:
            if progress_callback:
                progress_callback(processed, total_, msg, phase=phase, extra=extra)

        def _log(msg: str) -> None:
            if log_callback:
                log_callback(msg)

        total = len(df)
        if total < 2:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{"note": "Se necesitan al menos 2 filas"}],
            )

        columns = self.columns or kwargs.get("columns") or []
        available_cols = [c for c in columns if c in df.columns]
        if not available_cols:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=0, failed=0, failure_pct=0.0,
                details=[{"note": "Ninguna de las columnas seleccionadas existe en los datos"}],
                recommendation="Selecciona al menos una columna desde la vista previa",
            )

        col_types = {c: _classify_column(c) for c in available_cols}

        # Modo rápido: usa solo campos fuertes (id, nombre, apellido, fecha)
        if self.mode == "rapido":
            strong = [c for c in available_cols if col_types[c] in ("id", "name", "surname", "dob")]
            if len(strong) >= 2:
                use_cols = strong
            else:
                use_cols = available_cols
        else:
            use_cols = available_cols

        # Pesos: del usuario (renormalizados) o defaults por tipo
        if self.weights:
            w = {c: float(self.weights[c]) for c in use_cols if c in self.weights and float(self.weights[c]) > 0}
            if not w:
                w = {c: _default_field_weight(col_types[c]) for c in use_cols}
        else:
            w = {c: _default_field_weight(col_types[c]) for c in use_cols}
        use_cols = list(w.keys())
        total_w = sum(w.values())
        if total_w <= 0:
            w = {c: 1.0 for c in use_cols}
            total_w = len(w)
        weights = {c: v / total_w for c, v in w.items()}

        col_strs: dict[str, list[str]] = {}
        for c in use_cols:
            col_strs[c] = df[c].astype(str).fillna("").tolist()

        _log(f"Iniciando personas similares V2 (modo: {self.mode}) con {total:,} registros, campos: {', '.join(use_cols)}")

        # --- Blocking multi-paso ---
        _cb(0, total, "Generando pares candidatos...", phase="blocking")
        blocks: dict[str, list[int]] = defaultdict(list)
        for i in range(total):
            for c in use_cols:
                for key in self._block_keys(col_types[c], col_strs[c][i]):
                    blocks[key].append(i)
        capped_blocks = sum(1 for v in blocks.values() if len(v) > _MAX_BLOCK_SIZE)
        candidate_pairs = _pairs_from_blocks(blocks)
        if capped_blocks:
            _log(f"Aviso: {capped_blocks} bloques excedieron {_MAX_BLOCK_SIZE} registros y se truncaron")
        _cb(0, total, f"Bloqueo completo: {len(candidate_pairs):,} pares candidatos", phase="blocking")

        # --- Scoring con batching ---
        edges = []
        pair_scores: dict[tuple[int, int], dict] = {}
        pairs_list = list(candidate_pairs)
        total_pairs = len(pairs_list)
        BATCH = 5000
        num_batches = max(1, (total_pairs + BATCH - 1) // BATCH)
        if total_pairs > 0:
            _log(f"Generados {total_pairs:,} pares candidatos, scoring en {num_batches} lotes...")
            _cb(0, total_pairs, f"Iniciando scoring de {total_pairs:,} pares...", phase="scoring")

        batch_times: deque = deque(maxlen=5)
        field_sums: dict[str, float] = defaultdict(float)
        field_counts: dict[str, int] = defaultdict(int)
        score_buckets: dict[str, int] = {"bajo": 0, "medio": 0, "alto": 0}
        total_matches = 0
        for batch_idx in range(num_batches):
            start = batch_idx * BATCH
            end = min(start + BATCH, total_pairs)
            batch = pairs_list[start:end]
            batch_before = len(edges)
            t_batch = time.perf_counter()
            for i, j in batch:
                scores = {}
                for c in use_cols:
                    sim = self._field_sim(col_types[c], col_strs[c][i], col_strs[c][j])
                    scores[c] = sim
                    field_sums[c] += sim
                    field_counts[c] += 1
                composite = sum(weights[c] * scores[c] for c in use_cols)
                if composite >= self.threshold and composite < 1.0:
                    edges.append((i, j))
                    pair_scores[(i, j)] = {
                        "composite": round(composite, 4),
                        "fields": {c: round(scores[c], 4) for c in use_cols},
                    }
                if composite < self.threshold:
                    score_buckets["bajo"] += 1
                elif composite < 0.9:
                    score_buckets["medio"] += 1
                else:
                    score_buckets["alto"] += 1
            batch_times.append(time.perf_counter() - t_batch)
            batch_matches = len(edges) - batch_before
            total_matches += batch_matches
            processed = min(end, total_pairs)
            avg_batch = sum(batch_times) / len(batch_times)
            remaining = num_batches - batch_idx - 1
            eta_sec = round(remaining * avg_batch) if remaining > 0 else 0
            field_avgs = {k: round(field_sums[k] / field_counts[k], 4) for k in field_sums if field_counts[k] > 0}
            _extra = {
                "field_avgs": field_avgs,
                "score_distribution": dict(score_buckets),
                "eta_sec": eta_sec,
                "batch_matches": batch_matches,
                "total_matches": total_matches,
                "batch_pairs": len(batch),
            }
            _cb(processed, total_pairs, f"Comparando pares... ({processed:,} de {total_pairs:,})", phase="scoring", extra=_extra)
            if batch_matches > 0:
                _log(f"Lote {batch_idx + 1}/{num_batches}: {len(batch)} pares, {batch_matches} coincidencias")
            else:
                _log(f"Lote {batch_idx + 1}/{num_batches}: {len(batch)} pares, sin coincidencias")

        field_label = ", ".join(use_cols)
        _cb(total_pairs if total_pairs > 0 else total, total_pairs if total_pairs > 0 else total,
            "Agrupando componentes conectados...", phase="clustering")
        components = _find_connected_components(edges, set(range(total)))
        if not components:
            _log("No se encontraron personas potencialmente duplicadas")
            _cb(1, 1, "Completado")
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{
                    "note": f"No se encontraron personas potencialmente duplicadas (modo: {self.mode}, campos: {field_label})",
                    "columns": use_cols,
                    "weights": {k: round(v, 3) for k, v in weights.items()},
                    "threshold": self.threshold,
                }],
            )

        failed_rows = sum(len(c) for c in components)
        failure_pct = round((failed_rows / total) * 100, 2)
        groups_output = []
        sample_failures = []
        for comp in components[:100000]:
            group_rows = []
            comp_scores = []
            field_avgs_group: dict[str, float] = defaultdict(float)
            n_pairs = 0
            for a_idx in range(len(comp)):
                for b_idx in range(a_idx + 1, len(comp)):
                    i, j = comp[a_idx], comp[b_idx]
                    key = (i, j) if (i, j) in pair_scores else (j, i)
                    if key in pair_scores:
                        info = pair_scores[key]
                        comp_scores.append(info["composite"])
                        n_pairs += 1
                        for c, v in info["fields"].items():
                            field_avgs_group[c] += v
            for idx in comp:
                group_rows.append({"row": int(idx), "values": df.iloc[idx].to_dict()})
            avg_comp = round(sum(comp_scores) / len(comp_scores), 4) if comp_scores else 0.0
            field_avgs_norm = {c: round(v / n_pairs, 4) for c, v in field_avgs_group.items()} if n_pairs else {}
            groups_output.append({
                "group_size": len(comp),
                "composite_score": avg_comp,
                "fields": field_avgs_norm,
                "mode": self.mode,
                "columns": field_label,
                "rows": group_rows,
            })
            if len(sample_failures) < 100000:
                for gr in group_rows:
                    if len(sample_failures) < 100000:
                        sample_failures.append({
                            "row": gr["row"],
                            "values": gr["values"],
                            "group_idx": len(groups_output) - 1,
                            "group_info": {
                                "composite_score": avg_comp,
                                "group_size": len(comp),
                                "mode": self.mode,
                                "columns": field_label,
                                "fields": field_avgs_norm,
                            },
                        })

        _log(f"Finalizado: {len(components)} grupos, {failed_rows} registros ({failure_pct}%)")
        _cb(1, 1, "Completado")
        return RuleResult(
            rule_name=self.name, description=self.description, severity=self.severity,
            passed=False, total=total, failed=failed_rows, failure_pct=failure_pct,
            details=[{
                "type": "personas_similares_v2_groups",
                "groups": groups_output,
                "total_groups": len(components),
                "mode": self.mode,
                "columns": field_label,
                "threshold": self.threshold,
                "weights": {k: round(v, 3) for k, v in weights.items()},
            }],
            sample_failures=sample_failures,
            recommendation=(
                "Revisa los grupos de personas similares V2 detectados. "
                "Pueden ser la misma persona registrada dos veces con pequeñas diferencias."
            ),
        )
