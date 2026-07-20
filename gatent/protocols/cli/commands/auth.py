import asyncio
import getpass

import click
from rich.console import Console

from gatent.protocols.shared.engine_factory import build_engine

console = Console()


@click.group()
def auth():
    """Manage authentication profiles."""


@auth.command()
@click.argument("profile_id")
@click.option("--kind", type=click.Choice(["api_key", "session_login"]), default="api_key")
@click.pass_context
def setup(ctx, profile_id, kind):
    """Create a new auth profile (interactive)."""
    if kind == "api_key":
        secrets = {"token": getpass.getpass("API token: ")}
    else:
        username = click.prompt("Username")
        secrets = {"username": username, "password": getpass.getpass("Password: ")}
    asyncio.run(_setup(ctx.obj.get("profile"), profile_id, kind, secrets))


async def _setup(profile, profile_id, kind, secrets):
    engine = build_engine(profile)
    result = await engine.vault.create_profile({
        "profile_id": profile_id, "kind": kind, "secrets": secrets,
    })
    console.print(f"[green]Created auth profile[/] {result['profile_id']} ({kind})")


@auth.command(name="revoke")
@click.argument("profile_id")
@click.pass_context
def revoke_cmd(ctx, profile_id):
    """Revoke an auth profile."""
    asyncio.run(_revoke(ctx.obj.get("profile"), profile_id))


async def _revoke(profile, profile_id):
    engine = build_engine(profile)
    await engine.vault.revoke_profile(profile_id)
    console.print(f"[yellow]Revoked auth profile[/] {profile_id}")
