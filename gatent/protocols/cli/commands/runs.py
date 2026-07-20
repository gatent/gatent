import asyncio
import json

import click
from rich.console import Console
from rich.table import Table

from gatent.protocols.shared.engine_factory import build_engine

console = Console()


@click.group()
def runs():
    """Inspect run history."""


@runs.command(name="list")
@click.option("--module", default=None)
@click.option("--limit", default=20, type=int)
@click.pass_context
def list_cmd(ctx, module, limit):
    asyncio.run(_list(ctx.obj.get("profile"), module, limit))


async def _list(profile, module_id, limit):
    engine = build_engine(profile)
    records = await engine.state_store.list_runs(module_id=module_id, limit=limit)
    if not records:
        console.print("[yellow]No runs found.[/]")
        return
    table = Table(title="Recent runs")
    for col in ["Run ID", "Module", "Status", "Events", "Started"]:
        table.add_column(col)
    for r in records:
        table.add_row(r.run_id, r.module_id, r.status.value,
                      str(r.events_emitted), r.started_at.isoformat(timespec="seconds"))
    console.print(table)


@runs.command()
@click.argument("run_id")
@click.pass_context
def show(ctx, run_id):
    asyncio.run(_show(ctx.obj.get("profile"), run_id))


async def _show(profile, run_id):
    engine = build_engine(profile)
    record = await engine.state_store.read_run(run_id)
    if record is None:
        console.print(f"[red]Run not found:[/] {run_id}")
        return
    console.print(json.dumps(record.to_dict(), indent=2))
