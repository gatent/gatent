from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from gatent.core import Engine
from gatent.protocols.rest.dependencies import caller_identity, get_engine

router = APIRouter(tags=["runs"])


@router.get("/runs")
async def list_runs(
    module_id: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 50,
    engine: Engine = Depends(get_engine),
    _: dict = Depends(caller_identity),
) -> dict:
    records = await engine.state_store.list_runs(
        module_id=module_id, since=since, limit=limit
    )
    return {"runs": [r.to_dict() for r in records], "next_cursor": None}


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    engine: Engine = Depends(get_engine),
    _: dict = Depends(caller_identity),
) -> dict:
    record = await engine.state_store.read_run(run_id)
    if record is None:
        raise HTTPException(404, f"Run '{run_id}' not found")
    return record.to_dict()
