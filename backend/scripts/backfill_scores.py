"""Backfill reports.score and task_history.score with the real fractional value.

The score column was originally `integer` (initial migration), so float scores like
99.98 were truncated to 100 on POSTGRES. This script recomputes each report's score
from its stored result_json.results[] (failure_pct + severity) using the same formula
as qdata.core.score.calculate_score, and writes it back.

Run inside the backend container:  python -m scripts.backfill_scores
"""
import asyncio

from sqlalchemy import select

from qdata.db.models import Report, TaskHistory
from qdata.db.session import async_session_factory

WEIGHTS = {"error": 10, "warning": 5, "info": 2}


def recompute_score(results: list[dict]) -> tuple[float, str]:
    total_weight = 0
    total_penalty = 0
    for r in results:
        weight = WEIGHTS.get(r.get("severity"), 5)
        total_weight += weight * 100
        total_penalty += r.get("failure_pct", 0) * weight

    if total_weight == 0:
        return 100.0, "excelente"

    raw_score = max(0, 100 - (total_penalty / total_weight * 100))
    score = round(raw_score, 2)

    if score >= 90:
        label = "excelente"
    elif score >= 70:
        label = "aceptable"
    elif score >= 50:
        label = "deficiente"
    else:
        label = "critico"
    return score, label


async def main() -> None:
    async with async_session_factory() as s:
        reports = (await s.execute(select(Report))).scalars().all()
        updated = 0
        skipped = 0
        for rep in reports:
            results = (rep.result_json or {}).get("results", [])
            if not results:
                skipped += 1
                continue
            score, label = recompute_score(results)
            score_f = float(score)
            rep.score = score_f
            rep.label = label
            updated += 1

        # Sync task_history scores that reference a report (already recomputed above)
        histories = (await s.execute(select(TaskHistory))).scalars().all()
        score_by_report = {r.id: float(r.score) for r in reports if r.score is not None}
        for h in histories:
            if h.report_id and h.report_id in score_by_report:
                h.score = score_by_report[h.report_id]

        await s.commit()
        print(f"Updated {updated} reports, skipped {skipped} (no results)")

        # Show a summary of previously-rounded reports
        demo = (await s.execute(select(Report).order_by(Report.executed_at.desc()).limit(10))).scalars().all()
        for rep in demo:
            print(repr(rep.score), "|", rep.summary)


if __name__ == "__main__":
    asyncio.run(main())
