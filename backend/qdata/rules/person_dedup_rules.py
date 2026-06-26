import re
import unicodedata
from collections import defaultdict, deque

import numpy as np
import pandas as pd

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from qdata.rules.base import Rule, RuleResult

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


def _normalize(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _levenshtein_ratio(s1: str, s2: str) -> float:
    s1, s2 = _normalize(s1), _normalize(s2)
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if fuzz:
        return fuzz.ratio(s1, s2) / 100.0
    n, m = len(s1), len(s2)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            temp = dp[j]
            dp[j] = min(
                prev + (0 if s1[i - 1] == s2[j - 1] else 1),
                dp[j] + 1,
                dp[j - 1] + 1,
            )
            prev = temp
    return 1.0 - dp[m] / max(n, m)


def _token_sort_ratio(s1: str, s2: str) -> float:
    if fuzz:
        return fuzz.token_sort_ratio(_normalize(s1), _normalize(s2)) / 100.0
    return _levenshtein_ratio(s1, s2)


def _name_similarity(s1: str, s2: str) -> float:
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if fuzz:
        n1, n2 = _normalize(s1), _normalize(s2)
        return max(fuzz.WRatio(n1, n2) / 100.0, fuzz.token_sort_ratio(n1, n2) / 100.0)
    return _levenshtein_ratio(s1, s2)


def _id_similarity(id1: str, id2: str) -> float:
    if not id1 and not id2:
        return 1.0
    if not id1 or not id2:
        return 0.0
    s1, s2 = str(id1), str(id2)
    sim = _levenshtein_ratio(s1, s2)
    prefix1 = re.sub(r"[0-9]", "", s1)
    prefix2 = re.sub(r"[0-9]", "", s2)
    if prefix1 and prefix2 and _normalize(prefix1) != _normalize(prefix2):
        sim *= 0.7
    return sim


def _date_similarity(d1, d2, window_days: int = 3) -> float:
    try:
        d1, d2 = pd.Timestamp(d1), pd.Timestamp(d2)
    except (ValueError, TypeError):
        return 0.0
    if pd.isna(d1) or pd.isna(d2):
        return 0.0
    diff = abs((d1 - d2).days)
    if diff == 0:
        return 1.0
    if diff <= window_days:
        return 1.0 - (diff / (window_days * 2))
    return 0.0


def _text_similarity(s1: str, s2: str) -> float:
    return _levenshtein_ratio(s1, s2)


def _auto_detect_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    col_lower = {c: c.lower().strip() for c in df.columns}
    name_pat = ["nombre", "nomb", "name", "nombres", "full_name", "fullname", "first_name", "given_name", "primer_nombre", "segundo_nombre"]
    surname_pat = ["apellido", "apellid", "ape", "last_name", "surname", "apellidos"]
    id_pat = ["cedula", "cédula", "id", "identificacion", "identificación", "rut", "dni", "documento", "docu", "cc", "nro_documento", "num_doc", "numdoc", "nume"]
    dob_pat = ["fecha_nac", "fecha nac", "fecha de nacimiento", "birth", "nacimiento", "dob", "date_of_birth", "fecha_nacimiento", "fnac", "f_nac"]
    addr_pat = ["direccion", "dirección", "address", "dir", "domicilio", "calle", "carrera", "direc"]
    phone_pat = ["telefono", "teléfono", "telef", "tel", "phone", "celular", "cel", "movil", "móvil", "contacto"]
    email_pat = ["email", "correo", "mail", "e-mail", "electronic_mail"]
    detected: dict[str, list[str]] = {"name": [], "surname": [], "id": [], "dob": [], "address": [], "phone": [], "email": []}
    for col, lower in col_lower.items():
        if any(p in lower for p in name_pat):
            detected["name"].append(col)
        if any(p in lower for p in surname_pat):
            detected["surname"].append(col)
        if any(p in lower for p in id_pat):
            detected["id"].append(col)
        if any(p in lower for p in dob_pat):
            detected["dob"].append(col)
        if any(p in lower for p in addr_pat):
            detected["address"].append(col)
        if any(p in lower for p in phone_pat):
            detected["phone"].append(col)
        if any(p in lower for p in email_pat):
            detected["email"].append(col)
    return detected


def _find_connected_components(edges: list[tuple[int, int]], nodes: set[int]) -> list[list[int]]:
    adj = defaultdict(list)
    for i, j in edges:
        adj[i].append(j)
        adj[j].append(i)
    visited = set()
    components = []
    for node in nodes:
        if node not in visited:
            component = []
            q = deque([node])
            while q:
                v = q.popleft()
                if v not in visited:
                    visited.add(v)
                    component.append(v)
                    for u in adj.get(v, []):
                        if u not in visited:
                            q.append(u)
            component.sort()
            if len(component) >= 2:
                components.append(component)
    return components


_MAX_BLOCK_SIZE = 500


def _pairs_from_blocks(blocks: dict[str, list[int]], max_block: int = _MAX_BLOCK_SIZE) -> set[tuple[int, int]]:
    candidate_pairs: set[tuple[int, int]] = set()
    for key, indices in blocks.items():
        if len(indices) > max_block:
            indices = indices[:max_block]
        n = len(indices)
        for a in range(n):
            for b in range(a + 1, n):
                candidate_pairs.add((indices[a], indices[b]))
    return candidate_pairs


def _get_block_keys(names: list[str], col_name: str, df: pd.DataFrame, suffix_col_name: str | None = None) -> dict[str, list[int]]:
    blocks: dict[str, list[int]] = defaultdict(list)
    for i in range(len(names)):
        raw = str(df.iloc[i][col_name]) if col_name else names[i]
        name_key = _normalize(raw)[:1] if _normalize(raw) else "_"
        if suffix_col_name:
            suffix_raw = str(df.iloc[i].get(suffix_col_name, "")) if not pd.isna(df.iloc[i].get(suffix_col_name, None)) else ""
            suffix_key = _normalize(suffix_raw)[:1] if _normalize(suffix_raw) else "_"
            key = suffix_key + name_key
        else:
            key = name_key
        blocks[key].append(i)
    return blocks


class FuzzyNameMatch(Rule):
    name = "fuzzy_name_match"
    description = "Detecta registros con nombres muy similares (Levenshtein, token_sort, token_set)"

    def __init__(self, severity: str = "warning", threshold: float = 0.88, blocking: bool = True):
        super().__init__(severity)
        self.threshold = threshold
        self.blocking = blocking

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        cols = _auto_detect_columns(df)
        name_cols = cols.get("name", [])
        surname_cols = cols.get("surname", [])
        all_name_cols = name_cols + surname_cols
        if not all_name_cols:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=0, failed=0, failure_pct=0.0,
                details=[{"note": "No se detectaron columnas de nombre"}],
                recommendation="Incluye una columna con 'nombre' en el nombre",
            )
        primary = all_name_cols[0]
        primary_surname = surname_cols[0] if surname_cols else None
        total = len(df)
        if total < 2:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{"note": "Se necesitan al menos 2 filas"}],
            )
        def _get_full_name(idx: int) -> str:
            parts = []
            for c in all_name_cols:
                v = df.iloc[idx].get(c, None)
                if not pd.isna(v):
                    parts.append(str(v))
            return " ".join(parts)
        names_full = [_get_full_name(i) for i in range(total)]
        if self.blocking:
            blocks = _get_block_keys(names_full, primary, df, suffix_col_name=primary_surname)
        else:
            blocks = {"_all": list(range(total))}
        edges = []
        for key, indices in blocks.items():
            if len(indices) < 2:
                continue
            for a_idx in range(len(indices)):
                for b_idx in range(a_idx + 1, len(indices)):
                    i, j = indices[a_idx], indices[b_idx]
                    sim = _name_similarity(names_full[i], names_full[j])
                    if sim >= self.threshold and sim < 1.0:
                        edges.append((i, j))
        components = _find_connected_components(edges, set(range(total)))
        if not components:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{"note": "No se encontraron nombres similares"}],
            )
        failed_rows = sum(len(c) for c in components)
        failure_pct = round((failed_rows / total) * 100, 2)
        groups_output = []
        sample_failures = []
        for comp in components[:100000]:
            group_rows = []
            for idx in comp:
                group_rows.append({"row": int(idx), "values": df.iloc[idx].to_dict()})
            total_sim = 0.0
            count = 0
            for a_idx in range(len(comp)):
                for b_idx in range(a_idx + 1, len(comp)):
                    total_sim += _name_similarity(names_full[comp[a_idx]], names_full[comp[b_idx]])
                    count += 1
            avg_sim = round(total_sim / count, 4) if count else 0.0
            groups_output.append({"group_size": len(comp), "avg_similarity": avg_sim, "rows": group_rows})
            if len(sample_failures) < 100000:
                for gr in group_rows:
                    if len(sample_failures) < 100000:
                        sample_failures.append({
                            "row": gr["row"], "values": gr["values"],
                            "group_idx": len(groups_output) - 1,
                            "group_similarity": avg_sim,
                        })
        return RuleResult(
            rule_name=self.name, description=self.description, severity=self.severity,
            passed=False, total=total, failed=failed_rows, failure_pct=failure_pct,
            details=[{"type": "fuzzy_name_groups", "groups": groups_output, "total_groups": len(components)}],
            sample_failures=sample_failures,
            recommendation="Revisa los grupos de nombres similares; pueden ser duplicados de una misma persona",
        )


class FuzzyIdMatch(Rule):
    name = "fuzzy_id_match"
    description = "Detecta registros con ID/cédula muy similares (1-2 dígitos diferentes)"

    def __init__(self, severity: str = "warning", threshold: float = 0.85, blocking: bool = True):
        super().__init__(severity)
        self.threshold = threshold
        self.blocking = blocking

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        cols = _auto_detect_columns(df)
        id_cols = cols.get("id", [])
        if not id_cols:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=0, failed=0, failure_pct=0.0,
                details=[{"note": "No se detectaron columnas de identificación"}],
                recommendation="Incluye una columna con 'cedula' o 'id' en el nombre",
            )
        primary = id_cols[0]
        total = len(df)
        if total < 2:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{"note": "Se necesitan al menos 2 filas"}],
            )
        ids = df[primary].astype(str).fillna("").tolist()
        blocks = {"_all": list(range(total))}
        if self.blocking:
            prefix_blocks: dict[str, list[int]] = defaultdict(list)
            for i, v in enumerate(ids):
                digits = re.sub(r"[^0-9]", "", v)
                key = digits[:max(1, len(digits) - 2)] if len(digits) > 2 else "_"
                prefix_blocks[key].append(i)
            blocks = dict(prefix_blocks)
        edges = []
        for key, indices in blocks.items():
            if len(indices) < 2:
                continue
            for a_idx in range(len(indices)):
                for b_idx in range(a_idx + 1, len(indices)):
                    i, j = indices[a_idx], indices[b_idx]
                    sim = _id_similarity(ids[i], ids[j])
                    if sim >= self.threshold and sim < 1.0:
                        edges.append((i, j))
        components = _find_connected_components(edges, set(range(total)))
        if not components:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{"note": "No se encontraron IDs similares"}],
            )
        failed_rows = sum(len(c) for c in components)
        failure_pct = round((failed_rows / total) * 100, 2)
        groups_output = []
        sample_failures = []
        for comp in components[:100000]:
            group_rows = []
            for idx in comp:
                group_rows.append({"row": int(idx), "values": df.iloc[idx].to_dict()})
            total_sim = 0.0
            count = 0
            for a_idx in range(len(comp)):
                for b_idx in range(a_idx + 1, len(comp)):
                    total_sim += _id_similarity(ids[comp[a_idx]], ids[comp[b_idx]])
                    count += 1
            avg_sim = round(total_sim / count, 4) if count else 0.0
            groups_output.append({"group_size": len(comp), "avg_similarity": avg_sim, "rows": group_rows})
            if len(sample_failures) < 100000:
                for gr in group_rows:
                    if len(sample_failures) < 100000:
                        sample_failures.append({
                            "row": gr["row"], "values": gr["values"],
                            "group_idx": len(groups_output) - 1,
                            "group_similarity": avg_sim,
                        })
        return RuleResult(
            rule_name=self.name, description=self.description, severity=self.severity,
            passed=False, total=total, failed=failed_rows, failure_pct=failure_pct,
            details=[{"type": "fuzzy_id_groups", "groups": groups_output, "total_groups": len(components)}],
            sample_failures=sample_failures,
            recommendation="Revisa los IDs similares; pueden ser errores de digitación del mismo documento",
        )


class SimilarDob(Rule):
    name = "similar_dob"
    description = "Detecta registros con fechas de nacimiento muy cercanas (±días configurable)"

    def __init__(self, severity: str = "warning", window_days: int = 3, threshold: float = 0.70, blocking: bool = True):
        super().__init__(severity)
        self.window_days = window_days
        self.threshold = threshold
        self.blocking = blocking

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        cols = _auto_detect_columns(df)
        dob_cols = cols.get("dob", [])
        if not dob_cols:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=0, failed=0, failure_pct=0.0,
                details=[{"note": "No se detectaron columnas de fecha de nacimiento"}],
                recommendation="Incluye una columna con 'fecha_nac' o 'nacimiento' en el nombre",
            )
        primary = dob_cols[0]
        total = len(df)
        if total < 2:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{"note": "Se necesitan al menos 2 filas"}],
            )
        dates = df[primary].copy()
        if self.blocking:
            year_blocks: dict[str, list[int]] = defaultdict(list)
            for i, d in enumerate(dates):
                m = re.search(r"(\d{4})", str(d))
                key = m.group(1) if m else "_"
                year_blocks[key].append(i)
            blocks = dict(year_blocks)
        else:
            blocks = {"_all": list(range(total))}
        edges = []
        for key, indices in blocks.items():
            if len(indices) < 2:
                continue
            for a_idx in range(len(indices)):
                for b_idx in range(a_idx + 1, len(indices)):
                    i, j = indices[a_idx], indices[b_idx]
                    sim = _date_similarity(dates.iloc[i], dates.iloc[j], self.window_days)
                    if sim >= self.threshold and sim < 1.0:
                        edges.append((i, j))
        components = _find_connected_components(edges, set(range(total)))
        if not components:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{"note": "No se encontraron fechas de nacimiento cercanas"}],
            )
        failed_rows = sum(len(c) for c in components)
        failure_pct = round((failed_rows / total) * 100, 2)
        groups_output = []
        sample_failures = []
        for comp in components[:100000]:
            group_rows = []
            for idx in comp:
                group_rows.append({"row": int(idx), "values": df.iloc[idx].to_dict()})
            total_sim = 0.0
            count = 0
            for a_idx in range(len(comp)):
                for b_idx in range(a_idx + 1, len(comp)):
                    total_sim += _date_similarity(dates.iloc[comp[a_idx]], dates.iloc[comp[b_idx]], self.window_days)
                    count += 1
            avg_sim = round(total_sim / count, 4) if count else 0.0
            groups_output.append({"group_size": len(comp), "avg_similarity": avg_sim, "rows": group_rows})
            if len(sample_failures) < 100000:
                for gr in group_rows:
                    if len(sample_failures) < 100000:
                        sample_failures.append({
                            "row": gr["row"], "values": gr["values"],
                            "group_idx": len(groups_output) - 1,
                            "group_similarity": avg_sim,
                        })
        return RuleResult(
            rule_name=self.name, description=self.description, severity=self.severity,
            passed=False, total=total, failed=failed_rows, failure_pct=failure_pct,
            details=[{"type": "similar_dob_groups", "groups": groups_output, "total_groups": len(components)}],
            sample_failures=sample_failures,
            recommendation="Revisa las fechas cercanas; pueden ser la misma persona con DOB registrada incorrectamente",
        )


class PersonCompositeSimilarity(Rule):
    name = "person_composite_similarity"
    description = "Score compuesto (nombre+ID+DOB+dirección+teléfono) para detectar la misma persona con datos ligeramente diferentes"

    def __init__(
        self,
        severity: str = "warning",
        threshold: float = 0.80,
        weights: dict[str, float] | None = None,
        blocking: bool = True,
    ):
        super().__init__(severity)
        self.threshold = threshold
        self.weights = weights or {"name": 0.30, "id": 0.25, "dob": 0.15, "address": 0.10, "phone": 0.10, "email": 0.10}
        self.blocking = blocking

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        cols = _auto_detect_columns(df)
        detected = {k: v for k, v in cols.items() if v}
        if not detected:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=0, failed=0, failure_pct=0.0,
                details=[{"note": "No se detectaron columnas de persona (nombre, ID, DOB, dirección, teléfono)"}],
                recommendation="Asegúrate de incluir columnas con nombres descriptivos",
            )
        total = len(df)
        if total < 2:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{"note": "Se necesitan al menos 2 filas"}],
            )
        available = [k for k in self.weights if k in detected]
        if not available:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=0, failed=0, failure_pct=0.0,
                details=[{"note": "No hay campos de persona detectados para comparar"}],
            )
        active_weights = {k: self.weights[k] for k in available}
        total_w = sum(active_weights.values())
        active_weights = {k: v / total_w for k, v in active_weights.items()}
        name_cols = cols.get("name", [])
        surname_cols = cols.get("surname", [])
        all_name_cols = name_cols + surname_cols
        primary_id = (cols.get("id") or [None])[0]
        primary_dob = (cols.get("dob") or [None])[0]
        primary_addr = (cols.get("address") or [None])[0]
        primary_phone = (cols.get("phone") or [None])[0]
        primary_email = (cols.get("email") or [None])[0]

        # Pre-compute string arrays for all rows (avoids repeated df.iloc in _row_pair_score)
        _name_strs: list[str] = []
        if all_name_cols:
            for idx in range(total):
                parts = []
                for c in all_name_cols:
                    v = df.iloc[idx].get(c, None)
                    if not pd.isna(v):
                        parts.append(str(v))
                _name_strs.append(" ".join(parts))
        _id_strs: list[str] = df[primary_id].astype(str).fillna("").tolist() if primary_id else []
        _dob_vals = df[primary_dob].tolist() if primary_dob else []
        _addr_strs: list[str] = df[primary_addr].astype(str).fillna("").tolist() if primary_addr else []
        _phone_strs: list[str] = df[primary_phone].astype(str).fillna("").tolist() if primary_phone else []
        _email_strs: list[str] = df[primary_email].astype(str).fillna("").tolist() if primary_email else []

        def _row_pair_score(i: int, j: int) -> dict:
            scores = {}
            if _name_strs:
                scores["name"] = _name_similarity(_name_strs[i], _name_strs[j])
            if _id_strs:
                scores["id"] = _id_similarity(_id_strs[i], _id_strs[j])
            if _dob_vals:
                scores["dob"] = _date_similarity(_dob_vals[i], _dob_vals[j])
            if _addr_strs:
                scores["address"] = _text_similarity(_addr_strs[i], _addr_strs[j])
            if _phone_strs:
                scores["phone"] = _text_similarity(_phone_strs[i], _phone_strs[j])
            if _email_strs:
                scores["email"] = _text_similarity(_email_strs[i], _email_strs[j])
            composite = sum(scores.get(k, 0.0) * w for k, w in active_weights.items())
            return {"composite": round(composite, 4), "fields": {k: round(scores.get(k, 0.0), 4) for k in available}}

        if self.blocking and (name_cols or surname_cols):
            primary_name_col = name_cols[0] if name_cols else (surname_cols[0] if surname_cols else None)
            primary_surname_col = surname_cols[0] if surname_cols else None
            names_list = df[primary_name_col].astype(str).fillna("").tolist() if primary_name_col else []
            blocks = _get_block_keys(names_list, primary_name_col, df, suffix_col_name=primary_surname_col) if primary_name_col else {"_all": list(range(total))}
        else:
            blocks = {"_all": list(range(total))}

        edges = []
        pair_scores: dict[tuple[int, int], dict] = {}
        for key, indices in blocks.items():
            if len(indices) < 2:
                continue
            for a_idx in range(len(indices)):
                for b_idx in range(a_idx + 1, len(indices)):
                    i, j = indices[a_idx], indices[b_idx]
                    result = _row_pair_score(i, j)
                    if result["composite"] >= self.threshold and result["composite"] < 1.0:
                        edges.append((i, j))
                        pair_scores[(i, j)] = result

        components = _find_connected_components(edges, set(range(total)))
        if not components:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{
                    "note": "No se encontraron grupos de personas potencialmente duplicadas",
                    "available_fields": available,
                }],
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
                "available_fields": available,
                "rows": group_rows,
            })
            if len(sample_failures) < 100000:
                for gr in group_rows:
                    if len(sample_failures) < 100000:
                        sample_failures.append({
                            "row": gr["row"],
                            "values": gr["values"],
                            "group_idx": len(groups_output) - 1,
                            "group_info": {"composite_score": avg_comp, "group_size": len(comp)},
                        })

        return RuleResult(
            rule_name=self.name, description=self.description, severity=self.severity,
            passed=False, total=total, failed=failed_rows, failure_pct=failure_pct,
            details=[{
                "type": "person_composite_groups",
                "groups": groups_output,
                "total_groups": len(components),
                "available_fields": available,
                "weights": {k: round(v, 3) for k, v in active_weights.items()},
            }],
            sample_failures=sample_failures,
            recommendation="Revisa los grupos detectados; probablemente son la misma persona con errores menores de digitación",
        )


class SimilarPeopleCheck(Rule):
    name = "personas_similares"
    description = "Detecta personas potencialmente duplicadas combinando nombre, ID, fecha de nacimiento, dirección, teléfono y email"

    RAPIDO_WEIGHTS = {"name": 0.40, "id": 0.35, "dob": 0.25}
    PROFUNDO_WEIGHTS = {"name": 0.25, "id": 0.20, "dob": 0.15, "address": 0.15, "phone": 0.15, "email": 0.10}

    def __init__(self, severity: str = "warning", mode: str = "rapido", threshold: float | None = None, columns: list[str] | None = None):
        super().__init__(severity)
        self.mode = mode
        self.columns = columns
        if threshold is not None:
            self.threshold = threshold
        elif mode == "profundo":
            self.threshold = 0.70
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

    def _score_pair_rapido(self, i: int, j: int,
                           name_strs: list[str],
                           id_strs: list[str],
                           dob_vals: list) -> tuple[float, dict]:
        scores = {}
        if name_strs:
            scores["name"] = self._name_similarity_deep(name_strs[i], name_strs[j])
        if id_strs:
            scores["id"] = _id_similarity(id_strs[i], id_strs[j])
        if dob_vals:
            scores["dob"] = _date_similarity(dob_vals[i], dob_vals[j])
        w = self.RAPIDO_WEIGHTS
        total_w = sum(w[k] for k in scores if k in w)
        if total_w == 0:
            return 0.0, scores
        composite = sum(scores.get(k, 0.0) * w[k] for k in scores if k in w) / total_w
        return composite, scores

    def _score_pair_profundo(self, i: int, j: int,
                             name_strs: list[str],
                             id_strs: list[str],
                             dob_vals: list,
                             addr_strs: list[str],
                             phone_strs: list[str],
                             email_strs: list[str]) -> tuple[float, dict]:
        scores = {}
        if name_strs:
            scores["name"] = self._name_similarity_deep(name_strs[i], name_strs[j])
        if id_strs:
            scores["id"] = _id_similarity(id_strs[i], id_strs[j])
        if dob_vals:
            scores["dob"] = _date_similarity(dob_vals[i], dob_vals[j])
        if addr_strs:
            scores["address"] = _text_similarity(addr_strs[i], addr_strs[j])
        if phone_strs:
            scores["phone"] = _text_similarity(phone_strs[i], phone_strs[j])
        if email_strs:
            scores["email"] = _text_similarity(email_strs[i], email_strs[j])
        w = self.PROFUNDO_WEIGHTS
        total_w = sum(w[k] for k in scores if k in w)
        if total_w == 0:
            return 0.0, scores
        composite = sum(scores.get(k, 0.0) * w[k] for k in scores if k in w) / total_w
        return composite, scores

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        import math, time
        progress_callback = kwargs.get("progress_callback")
        log_callback = kwargs.get("log_callback")

        def _cb(processed: int, total_: int, msg: str, phase: str = "", extra: dict | None = None) -> None:
            if progress_callback:
                progress_callback(processed, total_, msg, phase=phase, extra=extra)

        def _log(msg: str) -> None:
            if log_callback:
                log_callback(msg)

        from collections import deque

        total = len(df)
        if total < 2:
            return RuleResult(
                rule_name=self.name, description=self.description, severity=self.severity,
                passed=True, total=total, failed=0, failure_pct=0.0,
                details=[{"note": "Se necesitan al menos 2 filas"}],
            )

        columns = self.columns or kwargs.get("columns")

        _log(f"Iniciando personas similares (modo: {self.mode}) con {total:,} registros...")

        if columns:
            # --- Explicit columns mode: compare selected columns directly ---
            available_cols = [c for c in columns if c in df.columns]
            if not available_cols:
                return RuleResult(
                    rule_name=self.name, description=self.description, severity=self.severity,
                    passed=True, total=0, failed=0, failure_pct=0.0,
                    details=[{"note": "Ninguna de las columnas seleccionadas existe en los datos"}],
                    recommendation="Selecciona columnas válidas desde la vista previa",
                )

            col_strs: dict[str, list[str]] = {}
            for c in available_cols:
                col_strs[c] = df[c].astype(str).fillna("").tolist()

            rapido = self.mode == "rapido"

            # Blocking
            _cb(0, total, "Generando pares candidatos...", phase="blocking")
            if rapido:
                first_col = available_cols[0]
                blocks: dict[str, list[int]] = defaultdict(list)
                for i in range(total):
                    raw = col_strs[first_col][i]
                    key = _normalize(raw)[:1] if _normalize(raw) else "_"
                    blocks[key].append(i)
                capped_blocks = sum(1 for v in blocks.values() if len(v) > _MAX_BLOCK_SIZE)
                candidate_pairs = _pairs_from_blocks(blocks)
                cap_msg = f" (bloques >{_MAX_BLOCK_SIZE} truncados: {capped_blocks})" if capped_blocks else ""
                _cb(0, total, f"Bloqueo por '{first_col}': {len(candidate_pairs):,} pares{cap_msg}", phase="blocking")
            else:
                # Multi-pass: block by first letter of EACH selected column
                candidate_pairs = set()
                for ci, c in enumerate(available_cols):
                    _cb(0, total, f"Bloqueando por columna '{c}' ({ci + 1}/{len(available_cols)})...", phase="blocking")
                    blocks = defaultdict(list)
                    for i in range(total):
                        raw = col_strs[c][i]
                        key = _normalize(raw)[:1] if _normalize(raw) else "_"
                        blocks[key].append(i)
                    candidate_pairs |= _pairs_from_blocks(blocks)
                _cb(0, total, f"Total: {len(candidate_pairs):,} pares candidatos", phase="blocking")

            # Scoring with batching
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
        else:
            # --- Auto-detect mode (legacy) ---
            cols = _auto_detect_columns(df)
            name_cols = cols.get("name", [])
            surname_cols = cols.get("surname", [])
            all_name_cols = name_cols + surname_cols
            id_cols = cols.get("id", [])
            dob_cols = cols.get("dob", [])
            addr_cols = cols.get("address", [])
            phone_cols = cols.get("phone", [])
            email_cols = cols.get("email", [])

            if not all_name_cols and not id_cols and not dob_cols:
                return RuleResult(
                    rule_name=self.name, description=self.description, severity=self.severity,
                    passed=True, total=0, failed=0, failure_pct=0.0,
                    details=[{"note": "No se detectaron columnas de persona (nombre, ID, fecha de nacimiento)"}],
                    recommendation="Incluye columnas con 'nombre', 'cedula' o 'fecha_nac' en el nombre, o selecciona columnas explícitamente",
                )

            # Pre-compute arrays
            name_strs = [self._build_name_string(df, i, all_name_cols) for i in range(total)] if all_name_cols else []
            primary_id = id_cols[0] if id_cols else None
            primary_dob = dob_cols[0] if dob_cols else None
            primary_addr = addr_cols[0] if addr_cols else None
            primary_phone = phone_cols[0] if phone_cols else None
            primary_email = email_cols[0] if email_cols else None

            id_strs = df[primary_id].astype(str).fillna("").tolist() if primary_id else []
            dob_vals = df[primary_dob].tolist() if primary_dob else []
            addr_strs = df[primary_addr].astype(str).fillna("").tolist() if primary_addr else []
            phone_strs = df[primary_phone].astype(str).fillna("").tolist() if primary_phone else []
            email_strs = df[primary_email].astype(str).fillna("").tolist() if primary_email else []

            # Blocking
            _cb(0, total, "Generando pares candidatos...", phase="blocking")
            if self.mode == "profundo":
                candidate_pairs = set()
                if all_name_cols:
                    _cb(0, total, "Bloqueando por nombres...", phase="blocking")
                    primary_name_col = name_cols[0] if name_cols else surname_cols[0]
                    primary_surname_col = surname_cols[0] if surname_cols else None
                    name_blocks = _get_block_keys(name_strs, primary_name_col if name_cols else "",
                                                  df, suffix_col_name=primary_surname_col)
                    candidate_pairs |= _pairs_from_blocks(name_blocks)
                if primary_id:
                    _cb(0, total, "Bloqueando por ID...", phase="blocking")
                    id_blocks = defaultdict(list)
                    for i, v in enumerate(id_strs):
                        digits = re.sub(r"[^0-9]", "", v)
                        key = digits[:max(2, len(digits) - 1)] if len(digits) > 3 else "_"
                        id_blocks[key].append(i)
                    candidate_pairs |= _pairs_from_blocks(id_blocks)
                if primary_dob:
                    _cb(0, total, "Bloqueando por fecha de nacimiento...", phase="blocking")
                    year_blocks = defaultdict(list)
                    for i, d in enumerate(dob_vals):
                        m = re.search(r"(\d{4})", str(d))
                        key = m.group(1) if m else "_"
                        year_blocks[key].append(i)
                    candidate_pairs |= _pairs_from_blocks(year_blocks)
            else:
                if all_name_cols:
                    _cb(0, total, "Bloqueando por nombres...", phase="blocking")
                    primary_name_col = name_cols[0] if name_cols else surname_cols[0]
                    primary_surname_col = surname_cols[0] if surname_cols else None
                    blocks = _get_block_keys(name_strs, primary_name_col if name_cols else "",
                                             df, suffix_col_name=primary_surname_col)
                else:
                    blocks = {"_all": list(range(total))}
                candidate_pairs = _pairs_from_blocks(blocks)
            _cb(0, total, f"Total: {len(candidate_pairs):,} pares candidatos", phase="blocking")

            # Scoring with batching
            edges = []
            pair_scores = {}
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
                    if self.mode == "profundo":
                        composite, scores = self._score_pair_profundo(
                            i, j, name_strs, id_strs, dob_vals, addr_strs, phone_strs, email_strs)
                    else:
                        composite, scores = self._score_pair_rapido(
                            i, j, name_strs, id_strs, dob_vals)
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

            field_label = "auto-detect"

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
