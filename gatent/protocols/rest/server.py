"""FastAPI app factory."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from gatent import __version__
from gatent.protocols.rest.dependencies import set_engine
from gatent.protocols.rest.routes import account, auth, events, health, modules, runs
from gatent.protocols.shared.engine_factory import build_engine


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    set_engine(build_engine())
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Gatent API",
        version=__version__,
        description="The web action layer for agents.",
        lifespan=_lifespan,
        openapi_url="/v1/openapi.json",
        docs_url="/v1/docs",
    )
    app.include_router(health.router, prefix="/v1")
    app.include_router(modules.router, prefix="/v1")
    app.include_router(runs.router, prefix="/v1")
    app.include_router(events.router, prefix="/v1")
    app.include_router(auth.router, prefix="/v1")
    app.include_router(account.router, prefix="/v1")
    return app


app = create_app()
