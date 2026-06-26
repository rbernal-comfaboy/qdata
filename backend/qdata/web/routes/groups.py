"""Rutas CRUD para grupos de análisis y dashboard consolidado."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from qdata.db.models import AnalysisGroup, Project, Report
from qdata.db.session import get_session
from qdata.auth.dependencies import get_current_user

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupCreate(BaseModel):
    name: str
    description: str | None = None
    color: str = "#6366f1"


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


@router.get("")
async def list_groups(
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AnalysisGroup).where(AnalysisGroup.user_id == user.id).order_by(AnalysisGroup.created_at.desc())
    )
    groups = result.scalars().all()

    out = []
    for g in groups:
        proj_count = await session.execute(
            select(func.count(Project.id)).where(Project.group_id == g.id)
        )
        pcount = proj_count.scalar() or 0

        report_count = await session.execute(
            select(func.count(Report.id)).join(Project).where(Project.group_id == g.id)
        )
        rcount = report_count.scalar() or 0

        last_report = await session.execute(
            select(Report.executed_at).join(Project).where(Project.group_id == g.id).order_by(Report.executed_at.desc()).limit(1)
        )
        last = last_report.scalar()

        out.append({
            "id": str(g.id),
            "name": g.name,
            "description": g.description,
            "color": g.color,
            "project_count": pcount,
            "report_count": rcount,
            "last_analysis": last.isoformat() if last else None,
            "created_at": g.created_at.isoformat() if g.created_at else None,
        })
    return out


@router.post("")
async def create_group(
    body: GroupCreate,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    g = AnalysisGroup(user_id=user.id, name=body.name, description=body.description, color=body.color)
    session.add(g)
    await session.commit()
    await session.refresh(g)
    return {"id": str(g.id), "name": g.name, "description": g.description, "color": g.color}


@router.put("/{group_id}")
async def update_group(
    group_id: UUID,
    body: GroupUpdate,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AnalysisGroup).where(AnalysisGroup.id == group_id, AnalysisGroup.user_id == user.id)
    )
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(404, "Grupo no encontrado")
    if body.name is not None:
        g.name = body.name
    if body.description is not None:
        g.description = body.description
    if body.color is not None:
        g.color = body.color
    await session.commit()
    return {"ok": True}


@router.delete("/{group_id}")
async def delete_group(
    group_id: UUID,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AnalysisGroup).where(AnalysisGroup.id == group_id, AnalysisGroup.user_id == user.id)
    )
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(404, "Grupo no encontrado")
    await session.delete(g)
    await session.commit()
    return {"ok": True}


@router.get("/{group_id}/dashboard")
async def group_dashboard(
    group_id: UUID,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AnalysisGroup).where(AnalysisGroup.id == group_id, AnalysisGroup.user_id == user.id)
    )
    g = result.scalar_one_or_none()
    if not g:
        raise HTTPException(404, "Grupo no encontrado")

    proj_result = await session.execute(
        select(Project).where(Project.group_id == group_id).order_by(Project.created_at.desc())
    )
    projects = proj_result.scalars().all()

    report_ids = []
    project_scores = []
    rule_stats = {}
    severity_counts = {"error": 0, "warning": 0, "info": 0}
    timeline = []

    for p in projects:
        rep_result = await session.execute(
            select(Report).where(Report.project_id == p.id).order_by(Report.executed_at.desc()).limit(1)
        )
        rep = rep_result.scalar_one_or_none()
        if rep:
            report_ids.append(str(rep.id))
            if rep.score is not None:
                project_scores.append({"name": p.name, "score": rep.score, "date": rep.executed_at.isoformat() if rep.executed_at else None})
            result_json = rep.result_json or {}
            for rule in result_json.get("results", []):
                rn = rule.get("rule_name", "unknown")
                if rn not in rule_stats:
                    rule_stats[rn] = {"passed": 0, "failed": 0, "total": 0}
                if rule.get("passed"):
                    rule_stats[rn]["passed"] += 1
                else:
                    rule_stats[rn]["failed"] += 1
                rule_stats[rn]["total"] += 1
                sev = rule.get("severity", "warning")
                if sev in severity_counts:
                    severity_counts[sev] += 1
            timeline.append({
                "date": rep.executed_at.isoformat() if rep.executed_at else None,
                "score": rep.score,
                "project": p.name,
            })

    avg_score = round(sum(s["score"] for s in project_scores) / len(project_scores), 2) if project_scores else 0
    total_projects = len(projects)
    total_reports = len(report_ids)
    total_rules_checked = sum(v["total"] for v in rule_stats.values())
    total_rules_passed = sum(v["passed"] for v in rule_stats.values())
    overall_pass_rate = round(total_rules_passed / total_rules_checked * 100, 2) if total_rules_checked else 0

    rule_summary = []
    for rn, v in rule_stats.items():
        rule_summary.append({
            "rule_name": rn,
            "passed": v["passed"],
            "failed": v["failed"],
            "total": v["total"],
            "pass_rate": round(v["passed"] / v["total"] * 100, 2) if v["total"] else 0,
        })
    rule_summary.sort(key=lambda x: x["failed"], reverse=True)

    return {
        "group": {"id": str(g.id), "name": g.name, "description": g.description, "color": g.color},
        "summary": {
            "total_projects": total_projects,
            "total_reports": total_reports,
            "avg_score": avg_score,
            "overall_pass_rate": overall_pass_rate,
            "total_rules_checked": total_rules_checked,
        },
        "scores_timeline": sorted(timeline, key=lambda x: x["date"] or ""),
        "project_scores": project_scores,
        "severity_counts": severity_counts,
        "rule_summary": rule_summary[:20],
    }
