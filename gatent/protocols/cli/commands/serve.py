import asyncio
import signal

import click
import uvicorn

from gatent.protocols.shared.engine_factory import build_engine


@click.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8200, type=int)
@click.option("--mcp-stdio", is_flag=True, help="Run MCP over stdio.")
@click.pass_context
def serve(ctx, host, port, mcp_stdio):
    """Start the Gatent server."""
    if mcp_stdio:
        from gatent.protocols.mcp.server import GatentMcpServer
        engine = build_engine(ctx.obj.get("profile"))
        asyncio.run(GatentMcpServer(engine).run_stdio())
        return
    config = uvicorn.Config("gatent.protocols.rest.server:app",
                            host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    async def _run():
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, server.handle_exit, sig, None)
        await server.serve()

    asyncio.run(_run())
