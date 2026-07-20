"""Gatent on Modal — cloud-profile deployment.

Modal is the execution substrate (browser runner + scheduler run here). The engine
is built by the canonical engine_factory (profile="cloud"), NOT hand-wired. REST is
the public/metered surface. MCP-over-HTTP is deferred (see KNOWN GAP); MCP-over-stdio
ships via the CLI today.

Deploy:  modal deploy gatent/deploy.py
Prereq:  modal secret gatent-secrets incl. GATENT_PROFILE=cloud.
"""
import modal

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install([
        "fastapi[standard]>=0.115", "uvicorn[standard]>=0.27", "httpx>=0.27",
        "pydantic>=2.7", "pyyaml>=6.0", "lxml>=5.0", "jsonpath-ng>=1.6",
        "croniter>=2.0", "click>=8.1", "rich>=13.7",
        "cryptography>=42.0", "boto3>=1.34", "asyncpg>=0.29",
        "supabase>=2.4", "notion-client>=2.2", "playwright>=1.44", "mcp>=1.0",
    ])
    .run_commands("playwright install --with-deps chromium")
    .add_local_python_source("gatent")
)

app = modal.App("gatent", image=image)
SECRETS = [modal.Secret.from_name("gatent-secrets")]   # MUST include GATENT_PROFILE=cloud
ARCHIVE = modal.Volume.from_name("gatent-run-archive", create_if_missing=True)
VOLUMES = {"/archive": ARCHIVE}


@app.function(secrets=SECRETS, volumes=VOLUMES, timeout=300, memory=2048, retries=1)
async def run_module(module_id: str, trigger: dict | None = None) -> dict:
    """Execute one Gatent module (a 'Gatent action') inside Modal."""
    from gatent.protocols.shared.engine_factory import build_engine
    engine = build_engine("cloud")
    record = await engine.run_module(module_id, trigger or {"type": "manual"})
    return record.to_dict()


@app.function(secrets=SECRETS, volumes=VOLUMES)
@modal.asgi_app()
def api():
    """Public REST surface (the metered API). Lifespan builds the cloud engine
    via GATENT_PROFILE=cloud."""
    from gatent.protocols.rest import create_app
    return create_app()


@app.function(secrets=SECRETS, schedule=modal.Cron("*/5 * * * *"))
async def scheduler_tick():
    """Fire any modules whose cron schedule is due (config in Notion)."""
    import asyncio
    from datetime import datetime, timezone
    from croniter import croniter
    from gatent.adapters.config_stores.notion import NotionConfigStore

    config = NotionConfigStore()
    modules = await config.list_modules()
    now = datetime.now(timezone.utc)
    due: list[str] = []
    for m in modules:
        sched = m.raw_config.get("schedule")
        if not sched:
            continue
        last = m.raw_config.get("last_run_at")
        if last is None or croniter(sched, datetime.fromisoformat(last)).get_next(datetime) <= now:
            due.append(m.module_id)
    if due:
        await asyncio.gather(
            *[run_module.remote.aio(mid) for mid in due],
            return_exceptions=True,
        )

# KNOWN GAP: no mcp() web endpoint in v0 — Protocol Pack P2 implements MCP over stdio
# only (GatentMcpServer.run_stdio); there is no SSE/HTTP ASGI app to mount. Remote
# MCP-over-HTTP requires implementing an SSE transport first. Local MCP works today:
# gatent serve --mcp-stdio
