import asyncio
import json
from datetime import datetime

import typer
from sqlalchemy import select

from qdata.core.config import settings
from qdata.db.models import ScheduledTask
from qdata.db.session import async_session_factory

scheduler_app = typer.Typer(help="Gestión de tareas programadas")


@scheduler_app.command("daemon")
def daemon():
    """Inicia el servicio de scheduler en background"""
    typer.echo("🔄 Iniciando QData Scheduler Daemon...")
    from qdata.scheduler.service import start_scheduler
    start_scheduler()
    typer.echo(f"✅ Scheduler iniciado en zona horaria: {settings.scheduler_timezone}")

    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        from qdata.scheduler.service import stop_scheduler
        stop_scheduler()
        typer.echo("👋 Scheduler detenido")


@scheduler_app.command("list")
def list_tasks():
    """Lista todas las tareas programadas"""

    async def _list():
        async with async_session_factory() as session:
            result = await session.execute(select(ScheduledTask))
            tasks = result.scalars().all()
            if not tasks:
                typer.echo("📭 No hay tareas programadas")
                return
            for t in tasks:
                typer.echo(f"  {t.id} | {t.name} | {t.cron_expr} | {t.status} | "
                           f"Último: {t.last_run or 'N/A'}")

    asyncio.run(_list())


@scheduler_app.command("run")
def run_task(
    task_id: str = typer.Argument(..., help="ID de la tarea"),
):
    """Ejecuta una tarea inmediatamente"""
    from qdata.scheduler.service import run_scheduled_task
    typer.echo(f"▶️ Ejecutando tarea {task_id}...")
    asyncio.run(run_scheduled_task(task_id))
    typer.echo("✅ Tarea ejecutada")


@scheduler_app.command("pause")
def pause_task(
    task_id: str = typer.Argument(..., help="ID de la tarea"),
):
    """Pausa una tarea programada"""
    from qdata.scheduler.service import pause_scheduled_task
    asyncio.run(pause_scheduled_task(task_id))
    typer.echo(f"⏸️ Tarea {task_id} pausada")


@scheduler_app.command("resume")
def resume_task(
    task_id: str = typer.Argument(..., help="ID de la tarea"),
):
    """Reanuda una tarea pausada"""
    from qdata.scheduler.service import resume_scheduled_task
    asyncio.run(resume_scheduled_task(task_id))
    typer.echo(f"▶️ Tarea {task_id} reanudada")
