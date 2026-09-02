"""Backfill existing stored sample_failures with full row data (values)."""

import datetime
import json
import math
import re
from decimal import Decimal

import pandas as pd
from sqlalchemy import create_engine, text

from qdata.core.loader import load_data
from qdata.rules.base import MAX_DUPE_ENTRIES, MAX_DUPE_GROUP_TOTAL
from qdata.rules.person_fields import email_columns, identity_field_columns

DB_URL = "postgresql://qdata:qdata_pass@postgres:5432/qdata"

MAX_LOAD_ROWS = 3000000

_CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def _clean_str(s):
    return _CONTROL_RE.sub("", s)


def _safe_val(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return bool(v)
    if isinstance(v, (int, float)):
        if math.isinf(v) or math.isnan(v):
            return str(v)
        v = float(v)
        return round(v, 6) if v != int(v) else int(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, datetime.timedelta):
        return v.total_seconds()
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    if isinstance(v, str):
        return _clean_str(v)
    if isinstance(v, dict):
        return {k: _safe_val(v) for k, v in v.items()}
    if isinstance(v, (list, tuple)):
        return [_safe_val(x) for x in v]
    try:
        if pd.isna(v):
            return None
    except (ValueError, TypeError):
        pass
    if hasattr(v, "item"):
        try:
            return _safe_val(v.item())
        except (ValueError, TypeError):
            return str(v)
    return str(v)


def _row_values(df, idx):
    row = df.loc[idx]
    return _safe_val({col: (v.item() if hasattr(v, "item") else v) for col, v in row.items()})


def _distinct_value_columns(result_json):
    cols = set()
    for rule in result_json.get("results", []):
        for sf in rule.get("sample_failures", []):
            if "rows" in sf:
                for m in sf["rows"]:
                    cols.update((m.get("values") or {}).keys())
            else:
                cols.update((sf.get("values") or {}).keys())
    return cols


def _is_partial(values, df_columns):
    """True when the stored values are missing columns vs the loaded df."""
    if not values:
        return True
    return set(values.keys()) != set(df_columns)


def _max_row_needed(result_json):
    """Return the maximum row index referenced across all sample_failures."""
    m = -1
    for rule in result_json.get("results", []):
        for sf in rule.get("sample_failures", []):
            if "rows" in sf:
                for member in sf["rows"]:
                    r = member.get("row")
                    if r is not None and r > m:
                        m = r
            r = sf.get("row")
            if r is not None and r > m:
                m = r
    return m


MAX_SAMPLE_FAILURES = 100
MAX_DUPE_ROWS_PER_GROUP = 10


def _rule_needs_dupe(rule):
    """True when a duplicate_check rule still has the legacy group format or is
    missing its per-row values."""
    sfs = rule.get("sample_failures") or []
    if not sfs:
        return False
    if any(isinstance(it, dict) and isinstance(it.get("rows"), list) for it in sfs):
        return True
    cols = _distinct_value_columns({"results": [rule]})
    return not cols


def _rule_needs_backfill(rule):
    if rule.get("rule_name") == "duplicate_check":
        return _rule_needs_dupe(rule)
    cols = _distinct_value_columns({"results": [rule]})
    if not cols:
        return True
    return len(cols) < 4


def _row_subset(df_sub, idx):
    if df_sub is None or idx not in df_sub.index:
        return None
    row = df_sub.loc[idx]
    return _safe_val({c: (row[c].item() if hasattr(row[c], "item") else row[c]) for c in df_sub.columns})


def _convert_duplicate_check(rule, df):
    """Convert legacy group-based duplicate_check sample_failures to per-row
    entries, build the duplicate_groups detail (identity-only rows), and attach
    identity+email values. Returns True if anything changed."""
    sfs = rule.get("sample_failures") or []
    if not sfs:
        return False

    id_cols = identity_field_columns(list(df.columns))
    email_cols = email_columns(list(df.columns))
    keep_email = id_cols + [c for c in email_cols if c not in id_cols] if id_cols else None
    df_id = df[id_cols] if id_cols else None
    df_keep = df[keep_email] if keep_email else None

    changed = False

    # Already per-row format → only refresh missing/partial values.
    if all(isinstance(it, dict) and "rows" not in it for it in sfs):
        detail = next((d for d in rule.get("details") or [] if d.get("type") == "duplicate_groups"), None)
        if detail is not None:
            for g in detail.get("groups") or []:
                for m in g.get("rows") or []:
                    if _is_partial(m.get("values"), set(df_id.columns)):
                        v = _row_subset(df_id, m.get("row"))
                        if v is not None:
                            m["values"] = v
                            changed = True
        for sf in sfs:
            if _is_partial(sf.get("values"), set(keep_email)):
                v = _row_subset(df_keep, sf.get("row"))
                if v is not None:
                    sf["values"] = v
                    changed = True
        return changed

    # Legacy group-based format → flatten to per-row.
    groups = []
    for item in sfs:
        rows = item.get("rows") or []
        idxs = [r.get("row") for r in rows if isinstance(r, dict) and r.get("row") is not None]
        if idxs:
            groups.append({"size": len(idxs), "rows": idxs})
    groups.sort(key=lambda g: g["size"], reverse=True)

    entries = []
    for g in groups:
        for r in g["rows"]:
            entries.append({"row": r, "group_size": g["size"]})
            if len(entries) >= MAX_DUPE_ENTRIES:
                break
        if len(entries) >= MAX_DUPE_ENTRIES:
            break

    groups_out = []
    total = 0
    for g in groups:
        take = min(len(g["rows"]), MAX_DUPE_GROUP_TOTAL - total)
        if take <= 0:
            break
        groups_out.append({"size": g["size"], "rows": [{"row": r} for r in g["rows"][:take]]})
        total += take

    for g in groups_out:
        for m in g["rows"]:
            v = _row_subset(df_id, m["row"])
            if v is not None:
                m["values"] = v
    for e in entries:
        v = _row_subset(df_keep, e["row"])
        if v is not None:
            e["values"] = v

    rule["sample_failures"] = entries
    details = [d for d in rule.get("details") or [] if d.get("type") != "duplicate_groups"]
    if groups_out:
        details.append({"type": "duplicate_groups", "groups": groups_out})
    rule["details"] = details
    return True


def _truncate_result(result_json):
    """Cap sample_failures like get_report does (old reports store unbounded
    failures, which become too large once full-row values are attached)."""
    for rule in result_json.get("results", []):
        sfs = rule.get("sample_failures")
        if not isinstance(sfs, list):
            continue
        if rule.get("rule_name") == "duplicate_check":
            legacy = any(isinstance(it, dict) and isinstance(it.get("rows"), list) for it in sfs)
            if not legacy:
                continue
            for item in sfs:
                if isinstance(item, dict):
                    rows = item.get("rows")
                    if isinstance(rows, list):
                        item["size"] = len(rows)
            sfs.sort(key=lambda it: (it.get("size") or 0) if isinstance(it, dict) else 0, reverse=True)
            capped = []
            for item in sfs[:MAX_SAMPLE_FAILURES]:
                if isinstance(item, dict):
                    rows = item.get("rows")
                    if isinstance(rows, list):
                        item["rows"] = rows[:MAX_DUPE_ROWS_PER_GROUP]
                capped.append(item)
            rule["sample_failures"] = capped
        elif len(sfs) > MAX_SAMPLE_FAILURES:
            rule["sample_failures"] = sfs[:MAX_SAMPLE_FAILURES]


def backfill_report(conn, report_id, source_config, result_json):
    st = source_config.get("source_type", "")
    cs = source_config.get("connection_string", "")
    q = source_config.get("query", "")
    fp = source_config.get("file_path", "")

    results = result_json.get("results", [])
    dupe_rules = [r for r in results if r.get("rule_name") == "duplicate_check" and r.get("sample_failures")]
    other_rules = [r for r in results if r.get("rule_name") != "duplicate_check"]
    needs = any(_rule_needs_dupe(r) for r in dupe_rules) or any(_rule_needs_backfill(r) for r in other_rules)
    if not needs:
        return True

    if not cs and not fp:
        print(f"  Skip: no connection_string or file_path")
        return False

    _truncate_result(result_json)

    max_row = _max_row_needed(result_json)
    nrows = min(max_row + 1000, MAX_LOAD_ROWS) if max_row >= 0 else None

    if max_row >= MAX_LOAD_ROWS:
        print(f"  Skip: needs row {max_row} but limit is {MAX_LOAD_ROWS}")
        return False

    try:
        df = load_data(st, cs, q, fp, nrows=nrows)
    except Exception as e:
        print(f"  Skip: cannot load data — {e}")
        return False

    if df.empty:
        print(f"  Skip: empty DataFrame")
        return False

    df_cols = set(df.columns)
    changed = False
    for rule in dupe_rules:
        changed = _convert_duplicate_check(rule, df) or changed
    for rule in other_rules:
        for sf in rule.get("sample_failures", []):
            if "rows" in sf:
                for member in sf["rows"]:
                    if _is_partial(member.get("values"), df_cols):
                        r = member.get("row")
                        if r is not None and r in df.index:
                            member["values"] = _row_values(df, r)
                            changed = True
                continue
            if _is_partial(sf.get("values"), df_cols):
                r = sf.get("row")
                if r is not None and r in df.index:
                    sf["values"] = _row_values(df, r)
                    changed = True

    if changed:
        new_json = _safe_val(result_json)
        conn.execute(
            text("UPDATE reports SET result_json = CAST(:json AS jsonb) WHERE id = :id"),
            {"json": json.dumps(new_json), "id": report_id},
        )
        print(f"  Updated")
    else:
        print(f"  No changes needed")
    return True


def main():
    import sys

    name_filter = sys.argv[1] if len(sys.argv) > 1 else "%"
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT r.id, r.result_json, p.source_config
            FROM reports r
            JOIN projects p ON r.project_id = p.id
            WHERE r.result_json IS NOT NULL
              AND p.source_config IS NOT NULL
              AND p.name LIKE :name_filter
            ORDER BY r.executed_at DESC
        """), {"name_filter": name_filter}).fetchall()

    print(f"Found {len(rows)} reports")
    ok = skip = 0

    engine = create_engine(DB_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        for row in rows:
            report_id = row[0]
            result_json = row[1]
            source_config = row[2]

            st = source_config.get("source_type", "")
            cs = source_config.get("connection_string", "")
            safe_cs = cs
            if "@" in cs:
                safe_cs = cs.split("@")[0].split(":")[0] + ":****@" + cs.split("@")[1]
            print(f"\n[{report_id}] type={st} conn={safe_cs[:80]}")

            try:
                done = backfill_report(conn, report_id, source_config, result_json)
                if done:
                    ok += 1
                else:
                    skip += 1
            except Exception as e:
                print(f"  Error: {e}")
                skip += 1

    print(f"\n{'='*60}")
    print(f"Done: {ok} updated, {skip} skipped/errors")


if __name__ == "__main__":
    main()
