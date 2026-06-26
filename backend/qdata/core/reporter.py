import json
from datetime import datetime

from jinja2 import Environment

from qdata.rules.base import RuleResult

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QData - Reporte de Calidad</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;padding:2rem}
.container{max-width:1200px;margin:0 auto}
.glass{background:rgba(255,255,255,0.15);backdrop-filter:blur(20px);
  -webkit-backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.3);
  border-radius:1rem;box-shadow:0 8px 32px rgba(0,0,0,0.1);padding:2rem;margin-bottom:2rem}
h1{color:#fff;font-size:2.5rem;margin-bottom:0.5rem}
h2{color:#fff;font-size:1.8rem;margin-bottom:1rem;border-bottom:2px solid rgba(255,255,255,0.2);padding-bottom:0.5rem}
h3{color:#fff;font-size:1.2rem;margin-bottom:0.8rem}
p,li{color:rgba(255,255,255,0.9);line-height:1.6}
.score-box{text-align:center;padding:2rem}
.score-number{font-size:5rem;font-weight:bold;color:#fff}
.score-label{font-size:1.5rem;padding:0.5rem 1.5rem;border-radius:2rem;display:inline-block;margin-top:1rem}
.excelente{background:rgba(72,187,120,0.4);color:#fff}
.aceptable{background:rgba(246,173,85,0.4);color:#fff}
.deficiente{background:rgba(237,137,54,0.4);color:#fff}
.critico{background:rgba(245,101,101,0.4);color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.5rem;margin-top:1.5rem}
.rule-card{padding:1.5rem;border-radius:0.8rem}
.rule-card.passed{background:rgba(72,187,120,0.2);border-left:4px solid #48bb78}
.rule-card.failed{background:rgba(245,101,101,0.2);border-left:4px solid #f56565}
.rule-card.warning{background:rgba(246,173,85,0.2);border-left:4px solid #f6ad55}
.rule-name{font-size:1rem;font-weight:600;color:#fff;margin-bottom:0.3rem}
.rule-desc{font-size:0.85rem;color:rgba(255,255,255,0.7);margin-bottom:0.5rem}
.rule-stat{font-size:0.9rem;color:rgba(255,255,255,0.9)}
.rec-box{background:rgba(255,255,255,0.1);padding:1rem;border-radius:0.5rem;margin-top:0.5rem}
.rec-box strong{color:#fff}
table{width:100%;border-collapse:collapse;margin-top:1rem}
th,td{text-align:left;padding:0.75rem;border-bottom:1px solid rgba(255,255,255,0.1);color:rgba(255,255,255,0.9)}
th{font-weight:600;color:#fff;background:rgba(255,255,255,0.05)}
.badge{padding:0.25rem 0.75rem;border-radius:1rem;font-size:0.75rem;font-weight:600}
.badge-error{background:rgba(245,101,101,0.3);color:#f56565}
.badge-warning{background:rgba(246,173,85,0.3);color:#f6ad55}
.badge-info{background:rgba(99,102,241,0.3);color:#a5b4fc}
.summary{color:rgba(255,255,255,0.85);font-size:1rem;margin-top:1rem;line-height:1.8}
</style>
</head>
<body>
<div class="container">
  <div class="glass score-box">
    <h1>QData</h1>
    <p>Reporte de Calidad de Datos</p>
    <div class="score-number">{{ score }}</div>
    <div class="score-label {{ label }}">{{ label|upper }}</div>
    <p class="summary">{{ summary }}</p>
  </div>

  <div class="glass">
    <h2>Resumen de Reglas</h2>
    <div class="grid">
    {% for r in results %}
      {% set cls = 'passed' if r.passed else 'failed' if r.severity == 'error' else 'warning' %}
      <div class="rule-card {{ cls }}">
        <div class="rule-name">{{ r.rule_name }}</div>
        <div class="rule-desc">{{ r.description }}</div>
        <div class="rule-stat">
          <span class="badge badge-{{ r.severity }}">{{ r.severity }}</span>
          Fallos: {{ r.failed }}/{{ r.total }} ({{ "%.2f"|format(r.failure_pct) }}%)
        </div>
        {% if r.recommendation %}
        <div class="rec-box"><strong>→</strong> {{ r.recommendation }}</div>
        {% endif %}
      </div>
    {% endfor %}
    </div>
  </div>

  {% if recommendations %}
  <div class="glass">
    <h2>Recomendaciones</h2>
    <table>
      <tr><th>Regla</th><th>Severidad</th><th>Recomendación</th></tr>
      {% for rec in recommendations %}
      <tr>
        <td>{{ rec.rule }}</td>
        <td><span class="badge badge-{{ rec.severity }}">{{ rec.severity }}</span></td>
        <td>{{ rec.recommendation }}</td>
      </tr>
      {% endfor %}
    </table>
  </div>
  {% endif %}

  {% if details %}
  <div class="glass">
    <h2>Detalle de Fallos</h2>
    {% for rule_name, dets in details.items() %}
      {% if dets %}
      <h3>{{ rule_name }}</h3>
      <table>
        <tr>
          {% for key in dets[0].keys() %}
          <th>{{ key }}</th>
          {% endfor %}
        </tr>
        {% for d in dets %}
        <tr>
          {% for val in d.values() %}
          <td>{{ val }}</td>
          {% endfor %}
        </tr>
        {% endfor %}
      </table>
      {% endif %}
    {% endfor %}
  </div>
  {% endif %}

  <div class="glass" style="text-align:center;font-size:0.8rem;color:rgba(255,255,255,0.5)">
    Generado por QData · {{ generated_at }}
  </div>
</div>
</body>
</html>"""


def generate_html_report(
    results: list[RuleResult],
    score: int,
    label: str,
    recommendations: list[dict],
    summary: str = "",
) -> str:
    details = {}
    for r in results:
        if r.details:
            details[r.rule_name] = r.details

    return HTML_TEMPLATE.format(
        score=score,
        label=label,
        results=results,
        recommendations=recommendations,
        details=details,
        summary=summary or f"Score de calidad: {score}/100 - {label.upper()}. "
                           f"Se ejecutaron {len(results)} reglas de validación.",
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )


def generate_json_report(
    results: list[RuleResult],
    score: int,
    label: str,
    profile: dict | None = None,
) -> str:
    report = {
        "score": score,
        "label": label,
        "generated_at": datetime.utcnow().isoformat(),
        "rules": [
            {
                "rule_name": r.rule_name,
                "description": r.description,
                "severity": r.severity,
                "passed": r.passed,
                "total": r.total,
                "failed": r.failed,
                "failure_pct": r.failure_pct,
                "recommendation": r.recommendation,
                "details": r.details,
            }
            for r in results
        ],
    }
    if profile:
        report["profile"] = profile
    return json.dumps(report, indent=2, default=str)


def generate_markdown_summary(results: list[RuleResult], score: int, label: str) -> str:
    lines = [f"# QData Reporte de Calidad\n", f"**Score:** {score}/100 ({label})\n"]
    for r in results:
        status = "✅" if r.passed else "❌"
        lines.append(f"{status} **{r.rule_name}**: {r.failed}/{r.total} ({r.failure_pct}%)")
        if r.recommendation:
            lines.append(f"   → {r.recommendation}")
    return "\n".join(lines)


PDF_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>QData - Reporte de Calidad</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Segoe UI',Roboto,sans-serif;background:#f0f2f6;padding:20px;color:#333}
  .container{max-width:1100px;margin:0 auto}
  .header{text-align:center;padding:30px;background:linear-gradient(135deg,#667eea,#764ba2);
    border-radius:12px;color:#fff;margin-bottom:20px}
  .header h1{font-size:28px;margin-bottom:4px}
  .header p{opacity:0.9;font-size:14px}
  .score{font-size:60px;font-weight:bold;margin:10px 0}
  .score-label{display:inline-block;padding:6px 24px;border-radius:20px;font-size:18px;font-weight:600}
  .label-excelente{background:rgba(72,187,120,0.85)}
  .label-aceptable{background:rgba(246,173,85,0.85)}
  .label-deficiente{background:rgba(237,137,54,0.85)}
  .label-critico{background:rgba(245,101,101,0.85)}
  .summary{margin-top:12px;font-size:14px;opacity:0.9}
  .section{background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,0.08)}
  .section h2{font-size:20px;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #eef2f7;color:#333}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .rule-card{padding:14px;border-radius:8px;border-left:4px solid}
  .rule-card.passed{background:#f0fdf4;border-color:#48bb78}
  .rule-card.failed{background:#fef2f2;border-color:#f56565}
  .rule-card.warning{background:#fffbeb;border-color:#f6ad55}
  .rule-card.info{background:#eff6ff;border-color:#6366f1}
  .rule-name{font-weight:600;font-size:14px;margin-bottom:2px}
  .rule-desc{font-size:12px;color:#666;margin-bottom:4px}
  .rule-stat{font-size:13px;color:#444}
  .badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}
  .badge-error{background:#f56565;color:#fff}
  .badge-warning{background:#f6ad55;color:#fff}
  .badge-info{background:#6366f1;color:#fff}
  .rec-box{background:#fffbeb;padding:8px 12px;border-radius:6px;margin-top:6px;font-size:12px}
  .detail-section{margin-top:12px}
  .detail-section h3{font-size:15px;margin-bottom:8px;color:#444}
  table{width:100%;border-collapse:collapse;font-size:11px;margin-top:6px}
  th{background:#f8fafc;text-align:left;padding:6px 8px;border-bottom:1px solid #e2e8f0;
    font-weight:600;color:#475569;font-size:11px}
  td{padding:5px 8px;border-bottom:1px solid #f1f5f9;color:#334155;font-size:11px}
  tr:nth-child(even){background:#f8fafc}
  .col-summary{padding:6px 10px;background:#f8fafc;border-radius:6px;margin-bottom:4px;font-size:12px}
  .footer{text-align:center;padding:16px;font-size:11px;color:#94a3b8}
  @media print{body{background:#fff;padding:0}.section{break-inside:avoid;box-shadow:none;border:1px solid #e2e8f0}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>QData</h1>
    <p>Reporte de Calidad de Datos</p>
    <div class="score">{{ score }}</div>
    <div class="score-label label-{{ label }}">{{ label|upper }}</div>
    <p class="summary">{{ summary }}</p>
  </div>

  <div class="section">
    <h2>Resumen de Reglas</h2>
    <div class="grid">
    {% for r in results %}
      {% set cls = 'passed' if r.passed else 'failed' if r.severity == 'error' else 'warning' if r.severity == 'warning' else 'info' %}
      <div class="rule-card {{ cls }}">
        <div class="rule-name">
          {{ r.rule_name }}
          <span class="badge badge-{{ r.severity }}">{{ r.severity }}</span>
        </div>
        <div class="rule-desc">{{ r.description }}</div>
        <div class="rule-stat">Fallos: {{ r.failed }}/{{ r.total }} ({{ "%.2f"|format(r.failure_pct) }}%)</div>
        {% if r.recommendation %}
        <div class="rec-box"><strong>→</strong> {{ r.recommendation }}</div>
        {% endif %}
      </div>
    {% endfor %}
    </div>
  </div>

  {% if recommendations %}
  <div class="section">
    <h2>Recomendaciones</h2>
    <table>
      <tr><th>Regla</th><th>Severidad</th><th>Recomendación</th></tr>
      {% for rec in recommendations %}
      <tr>
        <td>{{ rec.rule }}</td>
        <td><span class="badge badge-{{ rec.severity }}">{{ rec.severity }}</span></td>
        <td>{{ rec.recommendation }}</td>
      </tr>
      {% endfor %}
    </table>
  </div>
  {% endif %}

  {% if details %}
  <div class="section">
    <h2>Detalle por Regla</h2>
    {% for rule_name, dets in details.items() %}
    <div class="detail-section">
      <h3>{{ rule_name }}</h3>
      {% if dets.summary %}
      <div>
        {% for s in dets.summary %}
        <div class="col-summary">{{ s }}</div>
        {% endfor %}
      </div>
      {% endif %}
      {% if dets.errors %}
      <table>
        <tr><th>#</th><th>Fila</th><th>Columna</th><th>Valor</th><th>Descripción</th><th>Sugerencia</th></tr>
        {% for e in dets.errors %}
        <tr>
          <td>{{ e.idx }}</td>
          <td>{{ e.fila }}</td>
          <td>{{ e.columna }}</td>
          <td style="max-width:200px;word-break:break-all">{{ e.valor }}</td>
          <td>{{ e.descripcion }}</td>
          <td>{{ e.sugerencia }}</td>
        </tr>
        {% endfor %}
      </table>
      {% endif %}
    </div>
    {% endfor %}
  </div>
  {% endif %}

  <div class="footer">Generado por QData · {{ generated_at }}</div>
</div>
</body>
</html>"""


def generate_pdf_html(
    results: list[dict],
    score: int,
    label: str,
    recommendations: list[dict],
    summary: str = "",
) -> str:
    from qdata.core.descriptions import describe_detail, describe_error

    details = {}
    for r in results:
        rname = r.get("rule_name", "desconocida")
        rec = r.get("recommendation")
        summary_lines = []
        for d in r.get("details") or []:
            summary_lines.append(describe_detail(rname, d))
        error_rows = []
        for i, sf in enumerate(r.get("sample_failures") or []):
            info = describe_error(rname, sf, rec)
            error_rows.append({
                "idx": i + 1,
                "fila": info.get("fila") or "—",
                "columna": info.get("columna") or "—",
                "valor": info.get("valor") or "—",
                "descripcion": info.get("descripcion") or "",
                "sugerencia": info.get("sugerencia") or "",
            })
        if summary_lines or error_rows:
            details[rname] = {"summary": summary_lines, "errors": error_rows}

    from jinja2 import Environment, BaseLoader
    env = Environment(loader=BaseLoader(), autoescape=False)
    tmpl = env.from_string(PDF_HTML_TEMPLATE)
    return tmpl.render(
        score=score,
        label=label,
        results=results,
        recommendations=recommendations,
        details=details,
        summary=summary or f"Score de calidad: {score}/100 - {label.upper()}. Se ejecutaron {len(results)} reglas de validación.",
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )


def _pdf_text(text: str | int | float | None) -> str:
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    return text.replace("\u2014", "-").replace("\u2013", "-") \
               .replace("\u2018", "'").replace("\u2019", "'") \
               .replace("\u201c", '"').replace("\u201d", '"') \
               .replace("\u2026", "...").replace("\u2022", "*")


def generate_pdf(
    results: list[dict],
    score: int,
    label: str,
    recommendations: list[dict],
    summary: str = "",
) -> bytes:
    from qdata.core.descriptions import describe_detail, describe_error
    from fpdf import FPDF

    details = {}
    for r in results:
        rname = r.get("rule_name", "desconocida")
        rec = r.get("recommendation")
        summary_lines = []
        for d in r.get("details") or []:
            summary_lines.append(describe_detail(rname, d))
        error_rows = []
        for i, sf in enumerate(r.get("sample_failures") or []):
            info = describe_error(rname, sf, rec)
            error_rows.append({
                "idx": i + 1,
                "fila": _pdf_text(info.get("fila") or "-"),
                "columna": _pdf_text(info.get("columna") or "-"),
                "valor": _pdf_text(info.get("valor") or "-"),
                "descripcion": _pdf_text(info.get("descripcion") or ""),
                "sugerencia": _pdf_text(info.get("sugerencia") or ""),
            })
        if summary_lines or error_rows:
            details[rname] = {"summary": [_pdf_text(s) for s in summary_lines], "errors": error_rows}

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    page_w = 190
    margin = 10
    inner_w = page_w - 2 * margin

    def score_color(s):
        if s >= 70:
            return (34, 197, 94)
        elif s >= 50:
            return (234, 179, 8)
        return (239, 68, 68)

    def severity_fill(s):
        if s == "error":
            return (239, 68, 68)
        elif s == "warning":
            return (245, 158, 11)
        return (99, 102, 241)

    def severity_text(s):
        if s == "error":
            return (255, 255, 255)
        elif s == "warning":
            return (0, 0, 0)
        return (255, 255, 255)

    def header_block():
        pdf.set_fill_color(102, 126, 234)
        pdf.rect(0, 0, 210, 60, style="F")
        pdf.set_y(10)

        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 22)
        pdf.cell(page_w, 10, "QData - Reporte de Calidad de Datos", ln=True, align="C")

        sc = score_color(score)
        pdf.set_text_color(*sc)
        pdf.set_font("Helvetica", "B", 48)
        pdf.cell(page_w, 18, str(score), ln=True, align="C")

        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 14)
        label_upper = label.upper() if label else "N/A"
        lw = pdf.get_string_width(label_upper) + 12
        lx = (210 - lw) / 2
        pdf.set_fill_color(*sc)
        pdf.set_xy(lx, pdf.get_y() - 2)
        pdf.cell(lw, 8, f"  {label_upper}  ", ln=True, align="C", fill=True)

        pdf.set_xy(margin, pdf.get_y() + 2)
        pdf.set_text_color(230, 230, 255)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(inner_w, 5, _pdf_text(summary) or f"Score de calidad: {score}/100 - {label_upper}. Se ejecutaron {len(results)} reglas de validación.")

    header_block()

    def section_title(title):
        pdf.ln(6)
        pdf.set_text_color(51, 51, 51)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(inner_w, 8, title, ln=True)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(margin, pdf.get_y(), page_w - margin, pdf.get_y())
        pdf.ln(3)

    section_title("Resumen de Reglas")

    left_col_x = margin
    right_col_x = margin + inner_w / 2 + 4
    col_width = inner_w / 2 - 4
    card_height = 32

    for i, r in enumerate(results):
        col = i % 2
        x = left_col_x if col == 0 else right_col_x
        y = pdf.get_y()

        if y + card_height > 270:
            pdf.add_page()
            section_title("Resumen de Reglas (continuación)")
            y = pdf.get_y()

        passed = r.get("pass", r.get("passed", False))
        sev = r.get("severity", "info")

        if passed:
            bg = (240, 253, 244)
            border_clr = (72, 187, 120)
        elif sev == "error":
            bg = (254, 242, 242)
            border_clr = (239, 68, 68)
        elif sev == "warning":
            bg = (255, 251, 235)
            border_clr = (246, 173, 85)
        else:
            bg = (239, 246, 255)
            border_clr = (99, 102, 241)

        pdf.set_fill_color(*bg)
        pdf.set_draw_color(*border_clr)
        pdf.rect(x, y, col_width, card_height, style="DF")

        pie_r = 7
        px = x + col_width - pie_r - 5
        py = y + card_height / 2
        total_c = r.get("total", 0)
        rule_score = 100 - r.get("failure_pct", 0) if total_c > 0 else 100
        score_angle = 180 * rule_score / 100
        hole_r = 4.5

        pdf.set_fill_color(235, 235, 235)
        pdf.solid_arc(px, py, pie_r, 0, 360, clockwise=True, style="F")
        pdf.set_fill_color(255, 255, 255)
        pdf.circle(px, py, hole_r, style="F")

        if rule_score > 0:
            sc = score_color(rule_score)
            pdf.set_fill_color(*sc)
            pdf.set_draw_color(*sc)
            pdf.solid_arc(px, py, pie_r, 270, 270 + score_angle, clockwise=True, style="F")
            pdf.set_fill_color(255, 255, 255)
            pdf.circle(px, py, hole_r, style="F")

        pdf.set_draw_color(200, 200, 200)
        pdf.circle(px, py, pie_r)

        pdf.set_font("Helvetica", "B", 5.5)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(px - 3, py - 2.5)
        pdf.cell(6, 5, str(rule_score), align="C")

        pdf.set_xy(x + 3, y + 2)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "B", 9)
        rule_name = _pdf_text(r.get("rule_name", "?"))
        name_w = pdf.get_string_width(rule_name)
        pdf.cell(name_w, 5, rule_name)

        sev_fill = severity_fill(sev)
        sev_text_clr = severity_text(sev)
        sev_label = sev.upper()
        sw = pdf.get_string_width(sev_label) + 6
        pdf.set_fill_color(*sev_fill)
        pdf.set_text_color(*sev_text_clr)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(sw, 5, f" {sev_label} ", fill=True)

        pdf.set_xy(x + 3, y + 8)
        pdf.set_text_color(100, 100, 100)
        pdf.set_font("Helvetica", "", 7)
        desc = _pdf_text(r.get("description", ""))
        text_w = col_width - 6 - pie_r - 10
        pdf.multi_cell(max(text_w, 20), 3.5, desc)

        pdf.set_xy(x + 3, y + card_height - 6)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 8)
        failed = r.get("failed", 0)
        total = r.get("total", 0)
        pct = r.get("failure_pct", 0)
        pdf.cell(col_width - 6, 5, f"Fallos: {failed}/{total} ({pct:.1f}%)")

        if col == 1 or i == len(results) - 1:
            max_y = y + card_height + 3
            pdf.set_y(max_y)

    # Recommendations
    if recommendations:
        pdf.ln(4)
        s = pdf.get_y()
        pdf.add_page() if s > 240 else None
        section_title("Recomendaciones")

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)

        col_w = [50, 22, 108]
        headers = ["Regla", "Severidad", "Recomendación"]
        x0 = margin
        pdf.set_xy(x0, pdf.get_y())
        for j, (h, cw) in enumerate(zip(headers, col_w)):
            if j == 2:
                pass
            x = x0 + sum(col_w[:j])
            pdf.set_fill_color(248, 250, 252)
            pdf.set_text_color(71, 85, 105)
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(cw, 7, f" {h}", border=1, fill=True)

        pdf.ln()
        for rec in recommendations:
            rule = _pdf_text(rec.get("rule", "-"))
            sev = rec.get("severity", "info")
            rec_text = _pdf_text(rec.get("recommendation", "-"))
            h = 7

            if pdf.get_y() + h > 270:
                pdf.add_page()
                section_title("Recomendaciones (continuación)")

            y0 = pdf.get_y()
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(51, 51, 51)

            pdf.set_xy(x0, y0)
            pdf.cell(col_w[0], h, f" {rule}", border=1)

            pdf.set_font("Helvetica", "B", 7)
            sev_fill = severity_fill(sev)
            sev_text_clr = severity_text(sev)
            pdf.set_fill_color(*sev_fill)
            pdf.set_text_color(*sev_text_clr)
            pdf.cell(col_w[1], h, f" {sev.upper()} ", border=1, fill=True)

            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(51, 51, 51)
            pdf.cell(col_w[2], h, f" {rec_text}", border=1)
            pdf.ln()

    # Detail per rule
    if details:
        pdf.ln(4)
        s = pdf.get_y()
        pdf.add_page() if s > 200 else None
        section_title("Detalle por Regla")

        for rname, dets in details.items():
            if pdf.get_y() > 250:
                pdf.add_page()

            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(51, 51, 51)
            pdf.cell(inner_w, 7, _pdf_text(rname), ln=True)

            if dets.get("summary"):
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(100, 100, 100)
                for s_line in dets["summary"]:
                    if pdf.get_y() > 270:
                        pdf.add_page()
                    pdf.set_fill_color(248, 250, 252)
                    pdf.cell(inner_w, 5, f"  {_pdf_text(s_line)}", fill=True, ln=True)

            if dets.get("errors"):
                if pdf.get_y() > 250:
                    pdf.add_page()
                pdf.ln(2)
                err_cols = [8, 14, 22, 36, 50, 50]
                err_headers = ["#", "Fila", "Columna", "Valor", "Descripción", "Sugerencia"]
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_fill_color(248, 250, 252)
                pdf.set_text_color(71, 85, 105)
                x0 = margin
                for j, (h, cw) in enumerate(zip(err_headers, err_cols)):
                    x = x0 + sum(err_cols[:j])
                    pdf.set_xy(x, pdf.get_y())
                    pdf.cell(cw, 6, f" {h}", border=1, fill=True)
                pdf.set_xy(x0, pdf.get_y() + 6)

                for e in dets["errors"]:
                    if pdf.get_y() > 270:
                        pdf.add_page()
                        pdf.set_font("Helvetica", "B", 7)
                        pdf.set_fill_color(248, 250, 252)
                        pdf.set_text_color(71, 85, 105)
                        for j, (h, cw) in enumerate(zip(err_headers, err_cols)):
                            x = x0 + sum(err_cols[:j])
                            pdf.set_xy(x, pdf.get_y())
                            pdf.cell(cw, 6, f" {h}", border=1, fill=True)
                        pdf.set_xy(x0, pdf.get_y() + 6)

                    pdf.set_font("Helvetica", "", 7)
                    pdf.set_text_color(51, 51, 51)
                    vals = [
                        str(e.get("idx", "")),
                        str(e.get("fila", "")),
                        str(e.get("columna", "")),
                        str(e.get("valor", ""))[:50],
                        str(e.get("descripcion", ""))[:60],
                        str(e.get("sugerencia", ""))[:60],
                    ]
                    for j, (v, cw) in enumerate(zip(vals, err_cols)):
                        x = x0 + sum(err_cols[:j])
                        pdf.set_xy(x, pdf.get_y())
                        pdf.cell(cw, 5, f" {v}", border=1)
                    pdf.set_xy(x0, pdf.get_y() + 5)

            pdf.ln(4)

    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(page_w, 10, f"Generado por QData · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", align="C")

    return bytes(pdf.output(dest="S"))
