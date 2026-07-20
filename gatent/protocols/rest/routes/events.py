from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends

from gatent.core import Engine
from gatent.protocols.rest.dependencies import caller_identity, get_engine

router = APIRouter(tags=["events"])


@router.get("/events")
async def list_events(
    module_id: Optional[str] = None,
    type: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
    engine: Engine = Depends(get_engine),
    _: dict = Depends(caller_identity),
) -> dict:
    events = await engine.state_store.list_events(
        module_id=module_id, event_type=type, since=since, limit=limit
    )
    return {"events": [e.to_dict() for e in events], "next_cursor": None}
