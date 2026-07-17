import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from datetime import date, datetime
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import joinedload

from qdata.auth.dependencies import get_current_user
from qdata.auth.permissions import require_role
from qdata.core.descriptions import describe_detail, describe_error
from qdata.db.models import ErrorAction, GroupPermission, Project, Report, User
from qdata.db.session import get_session


class SetActionRequest(BaseModel):
    status: str

router = APIRouter()


@router.get("/")
@router.get("")
async def list_reports(
    group_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = 20,
    offset: int = 0,
):
    if user.role == "admin":
        query = select(Report).options(joinedload(Report.project))
    else:
        subq = select(GroupPermission.group_id).where(GroupPermission.user_id == user.id)
        query = (
            select(Report)
            .options(joinedload(Report.project))
            .where(
                or_(
                    Report.user_id == user.id,
                    Report.project.has(Project.group_id.in_(subq)),
                )
            )
        )
    if group_id:
        query = query.where(Report.project.has(group_id=group_id))
    if start_date:
        query = query.where(Report.executed_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.where(Report.executed_at <= datetime.combine(end_date, datetime.max.time()))
    result = await session.execute(
        query.order_by(Report.executed_at.desc()).offset(offset).limit(limit)
    )
    reports = result.unique().scalars().all()

    def _extract_names(sc: dict | None):
        if not sc:
            return None, None, None
        st = sc.get("source_type") or ""
        cs = sc.get("connection_string") or ""
        fp = sc.get("file_path") or ""
        query = sc.get("query") or ""
        import re as _re
        table_name = None
        if query:
            m = _re.search(r"FROM\s+[`\"']?(\w+)[`\"']?", query, _re.IGNORECASE)
            if m:
                table_name = m.group(1).upper()
        if st in ("mysql", "postgresql", "sqlite", "mssql"):
            source_label = table_name or st.upper()
            db_name = cs.rsplit("/", 1)[-1].split("?")[0] if "/" in cs else None
            connection_label = db_name.upper() if db_name else cs
        elif st == "file":
            source_label = "Archivo"
            connection_label = fp.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if fp else None
        else:
            source_label = st or "Desconocido"
            m = _re.search(r"(?:DATABASE|Database)=([^;]+)", cs)
            db_name = m.group(1).upper() if m else None
            if not db_name:
                db_name = cs.rsplit("/", 1)[-1].split("?")[0] if "/" in cs else None
            connection_label = db_name or cs or fp or None
        return source_label, connection_label, st

    return [
        {
            "id": str(r.id),
            "project_id": str(r.project_id),
            "project_name": r.project.name if r.project else None,
            "source_type": _extract_names(r.project.source_config if r.project else None)[2],
            "source_label": _extract_names(r.project.source_config if r.project else None)[0],
            "connection_label": _extract_names(r.project.source_config if r.project else None)[1],
            "score": r.score,
            "label": r.label,
            "summary": r.summary,
            "executed_at": r.executed_at.isoformat() if r.executed_at else None,
        }
        for r in reports
    ]


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if user.role == "admin":
        base_q = select(Report).options(joinedload(Report.project)).where(Report.id == report_id)
    else:
        subq = select(GroupPermission.group_id).where(GroupPermission.user_id == user.id)
        base_q = (
            select(Report)
            .options(joinedload(Report.project))
            .where(
                Report.id == report_id,
                or_(
                    Report.user_id == user.id,
                    Report.project.has(Project.group_id.in_(subq)),
                )
            )
        )
    result = await session.execute(base_q)
    report = result.unique().scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    source_query = None
    if report.project and report.project.source_config:
        source_query = report.project.source_config.get("query")
    return {
        "id": str(report.id),
        "project_id": str(report.project_id) if report.project_id else None,
        "project_name": report.project.name if report.project else None,
        "source_query": source_query,
        "score": report.score,
        "label": report.label,
        "result": report.result_json,
        "recommendations": report.recommendations,
        "summary": report.summary,
        "executed_at": report.executed_at.isoformat() if report.executed_at else None,
    }


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    user: User = Depends(require_role(["admin"])),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    await session.delete(report)
    await session.commit()
    return {"status": "deleted"}


@router.get("/{report_id}/rules/{rule_idx}/actions")
async def get_rule_actions(
    report_id: str,
    rule_idx: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ErrorAction).where(
            ErrorAction.report_id == report_id,
            ErrorAction.rule_index == rule_idx,
        )
    )
    actions = result.scalars().all()
    return [
        {
            "error_index": a.error_index,
            "status": a.status,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        }
        for a in actions
    ]


@router.put("/{report_id}/rules/{rule_idx}/errors/{error_idx}/action")
async def set_error_action(
    report_id: str,
    rule_idx: int,
    error_idx: int,
    body: SetActionRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if body.status not in ("sin_accion", "en_revision", "solucionado"):
        raise HTTPException(status_code=400, detail="Invalid status")
    result = await session.execute(
        select(ErrorAction).where(
            ErrorAction.report_id == report_id,
            ErrorAction.rule_index == rule_idx,
            ErrorAction.error_index == error_idx,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.status = body.status
        existing.updated_at = datetime.utcnow()
    else:
        action = ErrorAction(
            report_id=report_id,
            rule_index=rule_idx,
            error_index=error_idx,
            status=body.status,
        )
        session.add(action)
    await session.commit()
    return {"status": body.status}


@router.get("/{report_id}/export/excel")
async def export_report_excel(
    report_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if user.role == "admin":
        base_q = select(Report).where(Report.id == report_id)
    else:
        subq = select(GroupPermission.group_id).where(GroupPermission.user_id == user.id)
        base_q = (
            select(Report)
            .options(joinedload(Report.project))
            .where(
                Report.id == report_id,
                or_(
                    Report.user_id == user.id,
                    Report.project.has(Project.group_id.in_(subq)),
                )
            )
        )
    result = await session.execute(base_q)
    report = result.unique().scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    data = report.result_json or {}
    results = data.get("results", [])

    wb = Workbook()

    # --- Sheet 1: Resumen ---
    ws = wb.active
    ws.title = "Resumen"
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="6366F1", end_color="6366F1", fill_type="solid")

    ws.cell(1, 1, "Score").font = header_font
    ws.cell(1, 1).fill = header_fill
    ws.cell(1, 2, report.score)
    ws.cell(2, 1, "Etiqueta").font = header_font
    ws.cell(2, 1).fill = header_fill
    ws.cell(2, 2, report.label)
    ws.cell(3, 1, "Ejecutado").font = header_font
    ws.cell(3, 1).fill = header_fill
    ws.cell(3, 2, str(report.executed_at))
    ws.cell(4, 1, "Resumen").font = header_font
    ws.cell(4, 1).fill = header_fill
    ws.cell(4, 2, report.summary or "")
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 60

    # --- Sheet 2: Reglas ---
    ws2 = wb.create_sheet("Reglas")
    headers2 = ["Regla", "Descripción", "Severidad", "Aprobado", "Total", "Fallos", "% Fracaso", "Recomendación"]
    for ci, h in enumerate(headers2, 1):
        c = ws2.cell(1, ci, h)
        c.font = header_font
        c.fill = header_fill
    for ri, r in enumerate(results, 2):
        ws2.cell(ri, 1, r.get("rule_name", ""))
        ws2.cell(ri, 2, r.get("description", ""))
        ws2.cell(ri, 3, r.get("severity", ""))
        ws2.cell(ri, 4, "Sí" if r.get("passed") else "No")
        ws2.cell(ri, 5, r.get("total", 0))
        ws2.cell(ri, 6, r.get("failed", 0))
        ws2.cell(ri, 7, r.get("failure_pct", 0))
        ws2.cell(ri, 8, r.get("recommendation") or "")
    for ci in range(1, len(headers2) + 1):
        ws2.column_dimensions[chr(64 + ci)].width = 22

    # --- Sheet 3: Detalle por regla ---
    ws3 = wb.create_sheet("Detalle")
    row_idx = 1
    detail_headers = ["#", "Fila", "Columna", "Valor", "Descripción del error", "Sugerencia"]
    for r in results:
        rname = r.get("rule_name", "desconocida")
        recommendation = r.get("recommendation")
        details = r.get("details", [])
        sample_failures = r.get("sample_failures", [])

        # Section: Regla header
        total_failed = r.get("failed", 0)
        total_items = r.get("total", 0)
        failure_pct = r.get("failure_pct", 0)
        header_text = f"Regla: {rname}  —  {total_failed:,} errores de {total_items:,} registros ({failure_pct:.2f}%)"
        ws3.cell(row_idx, 1, header_text).font = Font(bold=True, size=12)
        row_idx += 1

        # Sub-section: Resumen por columna
        if details:
            ws3.cell(row_idx, 1, "Resumen por columna:").font = Font(bold=True, size=10, color="6366F1")
            row_idx += 1
            for d in details:
                ws3.cell(row_idx, 1, describe_detail(rname, d))
                row_idx += 1

        # Sub-section: Errores detallados
        if sample_failures:
            n_sample = len(sample_failures)
            note_text = (
                f"Mostrando {n_sample:,} de {total_failed:,} errores"
                if total_failed > n_sample else
                f"{n_sample:,} errores"
            )
            ws3.cell(row_idx, 1, note_text).font = Font(italic=True, size=9, color="888888")
            row_idx += 1
            # Get union of all keys in item.get("values") to display them as columns
            record_keys = []
            for item in sample_failures:
                vals = item.get("values")
                if vals and isinstance(vals, dict):
                    for k in vals.keys():
                        if k not in record_keys:
                            record_keys.append(k)

            headers = detail_headers + record_keys
            for ci, h in enumerate(headers, 1):
                c = ws3.cell(row_idx, ci, h)
                c.font = header_font
                c.fill = header_fill
            row_idx += 1

            error_counter = 0
            group_to_num = {}

            for item in sample_failures:
                info = describe_error(rname, item, recommendation)
                
                group_idx = item.get("group_idx")
                if group_idx is not None:
                    if group_idx not in group_to_num:
                        error_counter += 1
                        group_to_num[group_idx] = error_counter
                    current_err_num = group_to_num[group_idx]
                else:
                    error_counter += 1
                    current_err_num = error_counter

                ws3.cell(row_idx, 1, current_err_num)
                ws3.cell(row_idx, 2, info.get("fila") or "—")
                ws3.cell(row_idx, 3, info.get("columna") or "—")
                ws3.cell(row_idx, 4, info.get("valor") or "—")
                ws3.cell(row_idx, 5, info.get("descripcion") or "")
                ws3.cell(row_idx, 6, info.get("sugerencia") or "")
                
                # Write original record column values
                vals = item.get("values", {})
                for ki, k in enumerate(record_keys, 7):
                    val = vals.get(k)
                    ws3.cell(row_idx, ki, str(val) if val is not None else "—")

                row_idx += 1
        else:
            ws3.cell(row_idx, 1, "Sin errores de muestra")
            row_idx += 1

        row_idx += 1  # blank row between rules

    # Column widths
    ws3.column_dimensions["A"].width = 6
    ws3.column_dimensions["B"].width = 10
    ws3.column_dimensions["C"].width = 18
    ws3.column_dimensions["D"].width = 30
    ws3.column_dimensions["E"].width = 55
    ws3.column_dimensions["F"].width = 45

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=reporte_{report_id[:8]}.xlsx"},
    )


@router.get("/{report_id}/export/pdf")
async def export_report_pdf(
    report_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if user.role == "admin":
        base_q = select(Report).where(Report.id == report_id)
    else:
        subq = select(GroupPermission.group_id).where(GroupPermission.user_id == user.id)
        base_q = (
            select(Report)
            .options(joinedload(Report.project))
            .where(
                Report.id == report_id,
                or_(
                    Report.user_id == user.id,
                    Report.project.has(Project.group_id.in_(subq)),
                )
            )
        )
    result = await session.execute(base_q)
    report = result.unique().scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    data = report.result_json or {}
    results = data.get("results", [])
    recommendations = data.get("recommendations", [])

    from qdata.core.reporter import generate_pdf

    try:
        pdf_bytes = generate_pdf(
            results=results,
            score=report.score or 0,
            label=report.label or "N/A",
            recommendations=recommendations,
            summary=report.summary or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {e}")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=reporte_{report_id[:8]}.pdf"},
    )
