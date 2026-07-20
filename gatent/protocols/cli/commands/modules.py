import asyncio

import click
import yaml
from rich.console import Console
from rich.table import Table

from gatent.core import Module
from gatent.protocols.shared.engine_factory import build_engine

console = Console()


@click.group()
def modules():
    """Manage module configurations."""


@modules.command(name="list")
@click.option("--tag", default=None)
@click.pass_context
def list_cmd(ctx, tag):
    """List all configured modules."""
    asyncio.run(_list(ctx.obj.get("profile"), tag))


async def _list(profile, tag):
    engine = build_engine(profile)
    modules = await engine.config_store.list_modules(tag=tag)
    if not modules:
        console.print("[yellow]No modules found.[/]")
        return
    table = Table(title="Modules")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Tags")
    for m in modules:
        table.add_row(m.module_id, m.title, ", ".join(m.tags))
    console.print(table)


@modules.command()
@click.argument("module_id")
@click.pass_context
def show(ctx, module_id):
    """Show a module's configuration."""
    asyncio.run(_show(ctx.obj.get("profile"), module_id))


async def _show(profile, module_id):
    engine = build_engine(profile)
    try:
        module = await engine.config_store.load(module_id)
    except FileNotFoundError:
        console.print(f"[red]Module not found:[/] {module_id}")
        return
    console.print(yaml.safe_dump(module.raw_config, sort_keys=False))


@modules.command()
@click.argument("module_id")
@click.option("--template", type=click.Choice(["hn-watcher", "css-watcher", "json-api-watcher"]), default="hn-watcher")
@click.pass_context
def init(ctx, module_id, template):
    """Scaffold a new module from a template."""
    asyncio.run(_init(ctx.obj.get("profile"), module_id, template))


async def _init(profile, module_id, template):
    engine = build_engine(profile)
    config = _TEMPLATES[template].copy()
    config["title"] = config.get("title", module_id)
    module = Module(
        module_id=module_id,
        schema_version=config["schema_version"],
        module_version=config["module_version"],
        title=config["title"],
        description=config.get("description", ""),
        tags=config.get("tags", []),
        raw_config=config,
        auth_profile_id=config.get("auth_profile_id"),
    )
    await engine.config_store.save(module)
    console.print(f"[green]Created module[/] {module_id} from template '{template}'")


_HN_TEMPLATE = {
    "schema_version": 0, "module_version": "0.1.0",
    "title": "Hacker News Watcher",
    "description": "Watch the HN front page for new stories.",
    "tags": ["reading"],
    "navigate": {"steps": [{"type": "goto", "url": "https://news.ycombinator.com/"}]},
    "extract": {"type": "css", "row_selector": "tr.athing",
        "fields": {
            "id": {"selector": ".", "attr": "id"},
            "title": {"selector": ".titleline > a", "attr": "text"},
            "url": {"selector": ".titleline > a", "attr": "href"}}},
    "transform": [],
    "diff": {"identity_fields": ["id"], "emit_on": ["new_record"]},
    "route": [{"match": {"type": "new_record"}, "sinks": ["archive"], "notifiers": ["console"], "severity": "info"}],
    "sinks": {"archive": {"type": "json_lines", "path": "./events.jsonl"}},
    "notifiers": {"console": {"type": "stdout"}},
}

_CSS_TEMPLATE = {
    **{k: v for k, v in _HN_TEMPLATE.items()},
    "title": "CSS Watcher",
    "description": "Watch a page with CSS selectors. Replace URL and selectors.",
    "tags": ["watcher"],
    "navigate": {"steps": [{"type": "goto", "url": "https://example.com/"}]},
    "extract": {"type": "css", "row_selector": "div.item",
        "fields": {
            "id": {"selector": ".", "attr": "id"},
            "text": {"selector": ".", "attr": "text"}}},
}

_JSON_TEMPLATE = {
    **{k: v for k, v in _HN_TEMPLATE.items()},
    "title": "JSON API Watcher",
    "description": "Watch a JSON API endpoint. Replace URL and paths.",
    "tags": ["watcher"],
    "navigate": {"steps": [{"type": "goto", "url": "https://api.example.com/items"}]},
    "extract": {"type": "json_path", "row_path": "$.items[*]",
        "fields": {"id": "$.id", "name": "$.name"}},
}

_TEMPLATES = {
    "hn-watcher": _HN_TEMPLATE,
    "css-watcher": _CSS_TEMPLATE,
    "json-api-watcher": _JSON_TEMPLATE,
}
