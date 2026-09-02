import pandas as pd

from qdata.rules.base import MAX_DUPE_ENTRIES, MAX_DUPE_GROUP_TOTAL, Rule, RuleResult


class DuplicateCheck(Rule):
    name = "duplicate_check"
    description = "Detecta filas duplicadas exactas y parciales"

    def __init__(self, columns: list[str] | None = None, severity: str = "error"):
        super().__init__(severity=severity)
        self.columns = columns

    def execute(self, df: pd.DataFrame, **kwargs) -> RuleResult:
        if self.columns is not None:
            cols = [c for c in self.columns if c in df.columns]
            if not cols:
                cols = list(df.columns)
            df = df[cols]

        total_rows = len(df)
        df_str = df.astype(str).fillna("")
        exact_dupes = df_str.duplicated(keep=False)
        exact_count = int(exact_dupes.sum())
        exact_pct = round((exact_count / total_rows) * 100, 2) if total_rows else 0

        details = [{"type": "exact_duplicates", "count": exact_count, "pct": exact_pct}]

        sample_failures = []
        if exact_count > 0:
            dupes = df[exact_dupes]
            dupes_str = df_str[exact_dupes]
            grouped = dupes_str.groupby(list(df_str.columns))
            groups = []
            for _, group in grouped:
                members = [{"row": int(idx)} for idx in group.index]
                groups.append({"size": len(members), "rows": members})
            groups.sort(key=lambda g: g["size"], reverse=True)

            # One entry per duplicated row (values are attached later by the
            # analyze route, limited to identity + email columns).
            entries = []
            for g in groups:
                for m in g["rows"]:
                    entries.append({"row": m["row"], "group_size": g["size"]})
                    if len(entries) >= MAX_DUPE_ENTRIES:
                        break
                if len(entries) >= MAX_DUPE_ENTRIES:
                    break
            sample_failures = entries

            # Full groups (largest first) so the frontend can render every member.
            groups_out = []
            total = 0
            for g in groups:
                take = min(len(g["rows"]), MAX_DUPE_GROUP_TOTAL - total)
                if take <= 0:
                    break
                groups_out.append({"size": g["size"], "rows": [{"row": m["row"]} for m in g["rows"][:take]]})
                total += take
            if groups_out:
                details.append({"type": "duplicate_groups", "groups": groups_out})

        passed = exact_pct == 0
        recommendation = None
        if not passed:
            recommendation = "Eliminar duplicados exactos con df.drop_duplicates()"

        return RuleResult(
            rule_name=self.name,
            description=self.description,
            severity=self.severity,
            passed=passed,
            total=total_rows,
            failed=exact_count,
            failure_pct=exact_pct,
            details=details,
            sample_failures=sample_failures,
            recommendation=recommendation,
        )
