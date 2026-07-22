"""Backfill existing stored sample_failures with full row data (values)."""

import datetime
import json
import math
from decimal import Decimal

import pandas as pd
from sqlalchemy import create_engine, text

from qdata.core.loader import load_data

DB_URL = "postgresql://qdata:qdata_pass@postgres:5432/qdata"

MAX_LOAD_ROWS = 50000


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
        return v
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


def _needs_backfill(result_json):
    """Return True if any sample_failure lacks 'values'"""
    for rule in result_json.get("results", []):
        for sf in rule.get("sample_failures", []):
            if not sf.get("values"):
                if "rows" in sf:
                    for m in sf["rows"]:
                        if not m.get("values"):
                            return True
                else:
                    return True
    return False


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


def backfill_report(conn, report_id, source_config, result_json):
    st = source_config.get("source_type", "")
    cs = source_config.get("connection_string", "")
    q = source_config.get("query", "")
    fp = source_config.get("file_path", "")
    selected_columns = source_config.get("selected_columns")

    if not _needs_backfill(result_json):
        return True

    if not cs and not fp:
        print(f"  Skip: no connection_string or file_path")
        return False

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

    if selected_columns:
        sel = [c for c in selected_columns if c in df.columns]
        if sel:
            df = df[sel]
        else:
            df = df[list(df.columns)]

    changed = False
    for rule in result_json.get("results", []):
        for sf in rule.get("sample_failures", []):
            if sf.get("values"):
                continue
            if "rows" in sf:
                for member in sf["rows"]:
                    if member.get("values"):
                        continue
                    r = member.get("row")
                    if r is not None and r in df.index:
                        member["values"] = _row_values(df, r)
                        changed = True
                continue
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
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT r.id, r.result_json, p.source_config
            FROM reports r
            JOIN projects p ON r.project_id = p.id
            WHERE r.result_json IS NOT NULL
              AND p.source_config IS NOT NULL
            ORDER BY r.executed_at DESC
        """)).fetchall()

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
