"""DI: provides the singleton Engine to routes."""
from __future__ import annotations

from typing import Optional

from fastapi import Request
from fastapi.security import HTTPBearer

from gatent.core import Engine

_engine: Optional[Engine] = None
_bearer_scheme = HTTPBearer(auto_error=False)


def set_engine(engine: Engine) -> None:
    global _engine
    _engine = engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Engine not initialized; lifespan must run first.")
    return _engine


async def caller_identity(request: Request) -> dict:
    """v0 stub: solo_local has no real auth. Cloud profiles override."""
    creds = await _bearer_scheme(request)  # noqa: F841  reserved for cloud auth
    return {"kind": "user", "user_id": "local", "tier": "free", "scope": ["*"]}
