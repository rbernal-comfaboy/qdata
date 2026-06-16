import asyncio
import json

import typer

from qdata.cli.analyze_cmd import analyze
from qdata.cli.synthetic_cmd import synthetic
from qdata.cli.rules_cmd import rules
from qdata.cli.report_cmd import report
from qdata.cli.scheduler_cmd import scheduler_app
from qdata.core.config import settings

app = typer.Typer(
    name="qdata",
    help="QData - Sistema de Análisis de Calidad de Datos",
    no_args_is_help=True,
)

app.command(name="analyze")(analyze)
app.command(name="synthetic")(synthetic)
app.command(name="rules")(rules)
app.command(name="report")(report)
app.add_typer(scheduler_app, name="scheduler", help="Gestión de tareas programadas")


@app.callback()
def main():
    pass


def run_async(coro):
    return asyncio.run(coro)


if __name__ == "__main__":
    app()
