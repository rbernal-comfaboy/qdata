import typer

from qdata.synthetic.corruptors import corrupt
from qdata.synthetic.generator import generate_dataset
from qdata.synthetic.profiles import PROFILES


def synthetic(
    profile: str = typer.Option("ventas", "--profile", "-p", help="Perfil de datos"),
    rows: int = typer.Option(1000, "--rows", "-n", help="Número de filas"),
    output: str = typer.Option("", "--output", "-o", help="Archivo de salida (.csv, .xlsx, .json, .parquet)"),
    null_rate: float = typer.Option(0.0, "--null-rate", help="Tasa de nulos a introducir"),
    duplicate_rate: float = typer.Option(0.0, "--duplicate-rate", help="Tasa de duplicados"),
    outlier_rate: float = typer.Option(0.0, "--outlier-rate", help="Tasa de outliers"),
    typo_rate: float = typer.Option(0.0, "--typo-rate", help="Tasa de errores tipográficos"),
):
    """Genera datos sintéticos para pruebas"""
    if profile not in PROFILES:
        typer.echo(f"Perfiles disponibles: {list(PROFILES.keys())}", err=True)
        raise typer.Exit(1)

    typer.echo(f"📊 Generando {rows} filas del perfil '{profile}'...")
    df = generate_dataset(profile, rows)
    df = corrupt(df, null_rate=null_rate, duplicate_rate=duplicate_rate,
                 outlier_rate=outlier_rate, typo_rate=typo_rate)

    if output:
        ext = output.rsplit(".", 1)[-1].lower()
        if ext == "csv":
            df.to_csv(output, index=False)
        elif ext == "xlsx":
            df.to_excel(output, index=False)
        elif ext == "json":
            df.to_json(output, orient="records", indent=2)
        elif ext == "parquet":
            df.to_parquet(output, index=False)
        typer.echo(f"✅ Datos guardados: {output}")
    else:
        typer.echo(f"\nPrimeras 5 filas:")
        typer.echo(df.head().to_string())

    typer.echo(f"\n📊 {len(df)} filas x {len(df.columns)} columnas")
    typer.echo(f"   Columnas: {', '.join(df.columns)}")
