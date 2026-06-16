import typer

from qdata.core.engine import RULE_REGISTRY


def rules(
    list: bool = typer.Option(True, "--list", "-l", help="Listar reglas disponibles"),
):
    """Gestiona reglas de validación"""
    if list:
        typer.echo("📋 Reglas de validación disponibles:\n")
        for name, cls in RULE_REGISTRY.items():
            rule = cls()
            typer.echo(f"  • {name}")
            typer.echo(f"    {rule.description}")
            typer.echo(f"    Severidad: {rule.severity}")
            typer.echo()
