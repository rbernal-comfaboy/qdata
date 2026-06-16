import asyncio
from pathlib import Path

import typer

from qdata.core.engine import Engine, resolve_rules
from qdata.core.reporter import generate_html_report, generate_json_report, generate_markdown_summary
from qdata.core.score import build_recommendations, calculate_score


def analyze(
    db: str = typer.Option("", "--db", help="Connection string para base de datos"),
    query: str = typer.Option("", "--query", help="Consulta SQL"),
    file: str = typer.Option("", "--file", "-f", help="Ruta a archivo de datos"),
    source: str = typer.Option("csv", "--source", "-s", help="Tipo de fuente: csv, excel, json, parquet, postgresql, mysql, sqlserver, sqlite"),
    rules: str = typer.Option("all", "--rules", "-r", help="Reglas separadas por coma o 'all'"),
    output: str = typer.Option("report.html", "--output", "-o", help="Archivo de salida (.html, .json, .md)"),
    delimiter: str = typer.Option(",", "--delimiter", help="Delimitador para CSV"),
):
    """Ejecuta análisis de calidad de datos"""
    typer.echo("🔍 Cargando datos...")

    try:
        df = _load_data(source, db, query, file, delimiter)
    except Exception as e:
        typer.echo(f"❌ Error cargando datos: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"✅ Datos cargados: {len(df)} filas x {len(df.columns)} columnas")

    typer.echo("⚙️ Ejecutando reglas de validación...")
    engine = Engine(parallel=True)
    rule_list = resolve_rules(rules.split(",") if "," in rules else [rules])
    results = asyncio.run(engine.run(df, rule_list))

    score, label = calculate_score(results)
    recommendations = build_recommendations(results)

    typer.echo(f"\n📊 Score: {score}/100 ({label})")
    for r in results:
        status = "✅" if r.passed else "❌"
        typer.echo(f"  {status} {r.rule_name}: {r.failed}/{r.total} ({r.failure_pct}%)")

    ext = Path(output).suffix.lower()
    if ext == ".html":
        content = generate_html_report(results, score, label, recommendations)
    elif ext == ".json":
        content = generate_json_report(results, score, label)
    elif ext == ".md":
        content = generate_markdown_summary(results, score, label)
    else:
        content = generate_html_report(results, score, label, recommendations)

    Path(output).write_text(content, encoding="utf-8")
    typer.echo(f"\n📄 Reporte guardado: {output}")
    typer.echo("✅ Análisis completado")


def _load_data(source: str, db: str, query: str, file: str, delimiter: str):
    if db:
        if source == "postgresql":
            from qdata.connectors.postgres import PostgresConnector
            return PostgresConnector(db).load(query)
        elif source == "mysql":
            from qdata.connectors.mysql import MySQLConnector
            return MySQLConnector(db).load(query)
        elif source == "sqlserver":
            from qdata.connectors.sqlserver import SQLServerConnector
            return SQLServerConnector(db).load(query)
        elif source == "sqlite":
            from qdata.connectors.sqlite import SQLiteConnector
            return SQLiteConnector(file or "data.db").load(query)
    elif source == "csv":
        from qdata.connectors.csv_conn import CSVConnector
        return CSVConnector(file, delimiter=delimiter).load()
    elif source == "excel":
        from qdata.connectors.excel_conn import ExcelConnector
        return ExcelConnector(file).load()
    elif source == "json":
        from qdata.connectors.json_conn import JSONConnector
        return JSONConnector(file).load()
    elif source == "parquet":
        from qdata.connectors.parquet_conn import ParquetConnector
        return ParquetConnector(file).load()
    raise ValueError(f"Fuente no soportada: {source}")
