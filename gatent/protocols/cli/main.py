import click

from gatent import __version__
from gatent.protocols.cli.commands import auth, events, modules, run, runs, serve


@click.group(name="gatent")
@click.version_option(__version__)
@click.option("--profile", default=None, help="Profile to use (default: solo_local).")
@click.pass_context
def cli(ctx: click.Context, profile: str | None) -> None:
    """Gatent - the web action layer for agents."""
    ctx.ensure_object(dict)
    ctx.obj["profile"] = profile


cli.add_command(serve.serve)
cli.add_command(run.run)
cli.add_command(auth.auth)
cli.add_command(modules.modules)
cli.add_command(runs.runs)
cli.add_command(events.events)

if __name__ == "__main__":
    cli()
