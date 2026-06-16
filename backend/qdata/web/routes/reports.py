import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import joinedload

from qdata.auth.dependencies import get_current_user
from qdata.core.descriptions import describe_detail, describe_error
from qdata.db.models import Project, Report, User
from qdata.db.session import get_session

router = APIRouter()


@router.get("/")
async def list_reports(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = 20,
    offset: int = 0,
):
    result = await session.execute(
        select(Report)
        .options(joinedload(Report.project))
        .where(Report.user_id == user.id)
        .order_by(Report.executed_at.desc())
        .offset(offset)
        .limit(limit)
    )
    reports = result.unique().scalars().all()
    return [
        {
            "id": str(r.id),
            "project_id": str(r.project_id),
            "project_name": r.project.name if r.project else None,
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
    result = await session.execute(
        select(Report)
        .options(joinedload(Report.project))
        .where(Report.id == report_id, Report.user_id == user.id)
    )
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
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user.id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    await session.delete(report)
    await session.commit()
    return {"status": "deleted"}


@router.get("/{report_id}/export/excel")
async def export_report_excel(
    report_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user.id)
    )
    report = result.scalar_one_or_none()
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
        ws3.cell(row_idx, 1, f"Regla: {rname}").font = Font(bold=True, size=12)
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
            for ci, h in enumerate(detail_headers, 1):
                c = ws3.cell(row_idx, ci, h)
                c.font = header_font
                c.fill = header_fill
            row_idx += 1
            for i, item in enumerate(sample_failures):
                info = describe_error(rname, item, recommendation)
                ws3.cell(row_idx, 1, i + 1)
                ws3.cell(row_idx, 2, info.get("fila") or "—")
                ws3.cell(row_idx, 3, info.get("columna") or "—")
                ws3.cell(row_idx, 4, info.get("valor") or "—")
                ws3.cell(row_idx, 5, info.get("descripcion") or "")
                ws3.cell(row_idx, 6, info.get("sugerencia") or "")
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
    result = await session.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user.id)
    )
    report = result.scalar_one_or_none()
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
