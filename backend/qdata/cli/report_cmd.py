import json
from pathlib import Path

import typer


def report(
    input: str = typer.Option("report.json", "--input", "-i", help="Archivo JSON de reporte"),
    output: str = typer.Option("report.html", "--output", "-o", help="Archivo de salida"),
    format: str = typer.Option("html", "--format", "-f", help="Formato: html, json, md"),
):
    """Convierte reporte JSON a otros formatos"""
    data = json.loads(Path(input).read_text())
    score = data.get("score", 0)
    label = data.get("label", "unknown")
    recs = data.get("recommendations", [])

    ext = output.rsplit(".", 1)[-1].lower() if "." in output else format
    if ext == "html":
        from qdata.core.reporter import generate_html_report
        content = generate_html_report(data.get("rules", []), score, label, recs)
    elif ext == "md":
        from qdata.core.reporter import generate_markdown_summary
        content = generate_markdown_summary(data.get("rules", []), score, label)
    else:
        content = json.dumps(data, indent=2)

    Path(output).write_text(content, encoding="utf-8")
    typer.echo(f"✅ Reporte generado: {output}")
