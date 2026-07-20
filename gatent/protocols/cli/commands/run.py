import asyncio
import json
import sys

import click
from rich.console import Console

from gatent.protocols.shared.engine_factory import build_engine
from gatent.protocols.shared.error_mapping import map_error

console = Console()


@click.command()
@click.argument("module_id")
@click.option("--payload", default=None, help="JSON payload to pass.")
@click.pass_context
def run(ctx, module_id, payload):
    """Run a module once and print the result."""
    parsed = json.loads(payload) if payload else None
    asyncio.run(_run_async(ctx.obj.get("profile"), module_id, parsed))


async def _run_async(profile, module_id, payload):
    engine = build_engine(profile)
    try:
        record = await engine.run_module(module_id, payload or {"type": "manual"})
    except Exception as exc:
        m = map_error(exc)
        console.print(f"[red]Error:[/] {m.user_message}")
        if m.remediation:
            console.print(f"[yellow]Remediation:[/] {m.remediation}")
        sys.exit(m.cli_exit)
    console.print(f"[green]Run {record.run_id}:[/] {record.status.value}")
    console.print(f"  Events emitted: {record.events_emitted}")
    console.print(f"  Sinks: {record.sinks_succeeded} ok, {record.sinks_failed} failed")
    if record.error:
        console.print(f"  [red]Error:[/] {record.error}")
