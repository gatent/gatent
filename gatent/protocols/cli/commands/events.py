import asyncio
import json

import click
from rich.console import Console

from gatent.protocols.shared.engine_factory import build_engine

console = Console()


@click.group()
def events():
    """Inspect events."""


@events.command()
@click.option("--module", default=None)
@click.option("--limit", default=50, type=int)
@click.pass_context
def tail(ctx, module, limit):
    asyncio.run(_tail(ctx.obj.get("profile"), module, limit))


async def _tail(profile, module_id, limit):
    engine = build_engine(profile)
    events_list = await engine.state_store.list_events(module_id=module_id, limit=limit)
    if not events_list:
        console.print("[yellow]No events found.[/]")
        return
    color_map = {"info": "blue", "warning": "yellow", "error": "red", "critical": "red"}
    for e in reversed(events_list):
        sev = color_map[e.severity.value]
        console.print(f"[{sev}]{e.severity.value.upper()}[/] "
                      f"[dim]{e.timestamp.isoformat(timespec='seconds')}[/] "
                      f"[bold]{e.module_id}[/] [{e.type}] {json.dumps(e.payload)}")
