import re
import time
from collections import defaultdict, deque

import pandas as pd

from qdata.rules.base import Rule, RuleResult
from qdata.rules.person_dedup_v2 import _classify_column
from qdata.rules.person_dedup_rules import (
    _find_connected_components,
    _levenshtein_ratio,
    _normalize,
    _pairs_from_blocks,
    _token_sort_ratio,
)


class SimilarPeopleCheckV3(Rule):
    name = "personas_similares_v3"
    description = (
        "Personas similares V3: reproduce el comportamiento original de personas similares "
        "(modo profundo, columnas de identidad/nombre/apellido) que detectaba la misma persona "
        "registrada dos veces con pequeñas diferencias (cédula con dígito cambiado, mismo nombre, etc.)"
    )

    def __init__(
        self,
        severity: str = "warning",
        mode: str = "profundo",
        threshold: float | None = None,
        columns: list[str] | None = None,
    ):
        super().__init__(severity)
        self.mode = mode
        self.columns = columns
        if threshold is not None:
            self.threshold = threshold
        elif mode == "profundo":
            self.threshold = 0.90
        else:
            self.threshold = 0.80

    def _build_name_string(self, df: pd.DataFrame, idx: int, all_name_cols: list[str]) -> str:
        parts = []
        for c in all_name_cols:
            v = df.iloc[idx].get(c, None)
            if not pd.isna(v):
                parts.append(str(v))
        return " ".join(parts)

    def _name_similarity_deep(self, s1: str, s2: str) -> float:
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        n1, n2 = _normalize(s1), _normalize(s2)
        lev = _levenshtein_ratio(n1, n2)
        tok = _token_sort_ratio(n1, n2)
        return max(lev, tok)

    def _col_similarity_rapido(self, a: str, b: str) -> float:
        return _token_sort_ratio(a, b)

    def _col_similarity_profundo(self, a: str, b: str) -> float:
        return self._name_similarity_deep(a, b)

    def _score_pair_columns(self, i: int, j: int, col_strs: dict[str, list[str]], rapido: bool) -> tuple[float, dict]:
        scores = {}
        for col_name, vals in col_strs.items():
            a = vals[i] if i < len(vals) else ""
            b = vals[j] if j < len(vals) else ""
            if not a and not b:
                sim = 1.0
            elif not a or not b:
                sim = 0.0
            else:
                sim = self._col_similarity_rapido(a, b) if rapido else self._col_similarity_profundo(a, b)
            scores[col_name] = sim
        n = len(scores)
        composite = sum(scores.values()) / n if n > 0 else 0.0
        return composite, scores

    def _default_columns(self, df: pd.DataFrame) -> list[str]:
        cols = df.columns.tolist()
        classified = {c: _classify_column(c) for c in cols}
        id_cols = [c for c in cols if classified[c] == "id"]
        pk_cols = [c for c in id_cols if re.search(r"^(per)?id$|_id$", c, re.I)]
        if len(id_cols) > len(pk_cols):
            id_cols = [c for c in id_cols if c not in pk_cols]
        name_cols = [c for c in cols if classified[c] == "name"]
        surname_cols = [c for c in cols if classified[c] == "surname"]
        return id_cols + name_cols + surname_cols

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        import math, re

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

        columns = self.columns or kwargs.get("columns") or self._default_columns(df)
        available_cols = [c for c in columns if c in df.columns]
        if not available_cols:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=0, failed=0, failure_pct=0.0,
                details=[{"note": "No se detectaron columnas de persona (identificación, nombre, apellido)"}],
                recommendation="Incluye columnas con 'cedula', 'identificacion', 'nombre' o 'apellido' en el nombre, o selecciona columnas explícitamente",
            )

        col_strs: dict[str, list[str]] = {}
        for c in available_cols:
            col_strs[c] = df[c].astype(str).fillna("").tolist()

        rapido = self.mode == "rapido"

        _log(f"Iniciando personas similares V3 (modo: {self.mode}) con {total:,} registros, columnas: {', '.join(available_cols)}")

        # --- Blocking multi-paso: por primera letra de CADA columna ---
        _cb(0, total, "Generando pares candidatos...", phase="blocking")
        if rapido:
            first_col = available_cols[0]
            blocks: dict[str, list[int]] = defaultdict(list)
            for i in range(total):
                raw = col_strs[first_col][i]
                key = _normalize(raw)[:1] if _normalize(raw) else "_"
                blocks[key].append(i)
            candidate_pairs = _pairs_from_blocks(blocks)
            _cb(0, total, f"Bloqueo por '{first_col}': {len(candidate_pairs):,} pares", phase="blocking")
        else:
            candidate_pairs: set[tuple[int, int]] = set()
            for ci, c in enumerate(available_cols):
                _cb(0, total, f"Bloqueando por columna '{c}' ({ci + 1}/{len(available_cols)})...", phase="blocking")
                blocks = defaultdict(list)
                for i in range(total):
                    raw = col_strs[c][i]
                    key = _normalize(raw)[:1] if _normalize(raw) else "_"
                    blocks[key].append(i)
                candidate_pairs |= _pairs_from_blocks(blocks)
            _cb(0, total, f"Total: {len(candidate_pairs):,} pares candidatos", phase="blocking")

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
                composite, scores = self._score_pair_columns(i, j, col_strs, rapido)
                if composite >= self.threshold and composite < 1.0:
                    edges.append((i, j))
                    pair_scores[(i, j)] = {"composite": round(composite, 4), "fields": {k: round(v, 4) for k, v in scores.items()}}
                for k, v in scores.items():
                    field_sums[k] += v
                    field_counts[k] += 1
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

        field_label = ", ".join(available_cols)

        _cb(total_pairs if total_pairs > 0 else total, total_pairs if total_pairs > 0 else total,
            "Agrupando componentes conectados...", phase="clustering")
        components = _find_connected_components(edges, set(range(total)))
        if not components:
            _log("No se encontraron personas potencialmente duplicadas")
            _cb(1, 1, "Completado")
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{"note": f"No se encontraron personas potencialmente duplicadas (modo: {self.mode}, columnas: {field_label})"}],
            )

        failed_rows = sum(len(c) for c in components)
        failure_pct = round((failed_rows / total) * 100, 2)
        groups_output = []
        sample_failures = []
        for comp in components[:100000]:
            group_rows = []
            comp_scores = []
            for a_idx in range(len(comp)):
                for b_idx in range(a_idx + 1, len(comp)):
                    i, j = comp[a_idx], comp[b_idx]
                    key = (i, j) if (i, j) in pair_scores else (j, i)
                    if key in pair_scores:
                        comp_scores.append(pair_scores[key]["composite"])
            for idx in comp:
                group_rows.append({"row": int(idx), "values": df.iloc[idx].to_dict()})
            avg_comp = round(sum(comp_scores) / len(comp_scores), 4) if comp_scores else 0.0
            groups_output.append({
                "group_size": len(comp),
                "composite_score": avg_comp,
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
                            "group_info": {"composite_score": avg_comp, "group_size": len(comp), "mode": self.mode, "columns": field_label},
                        })

        _log(f"Finalizado: {len(components)} grupos, {failed_rows} registros ({failure_pct}%)")
        _cb(1, 1, "Completado")
        return RuleResult(
            rule_name=self.name, description=self.description, severity=self.severity,
            passed=False, total=total, failed=failed_rows, failure_pct=failure_pct,
            details=[{
                "type": "personas_similares_groups",
                "groups": groups_output,
                "total_groups": len(components),
                "mode": self.mode,
                "columns": field_label,
            }],
            sample_failures=sample_failures,
            recommendation=(
                "Revisa los grupos de personas similares detectados. "
                "Pueden ser duplicados de la misma persona con errores de captura."
            ),
        )
