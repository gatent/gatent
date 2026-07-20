"""v0: kind=api_key and kind=session_login (Flow A only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from gatent.core import Engine
from gatent.protocols.rest.dependencies import caller_identity, get_engine

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/profiles", status_code=201)
async def create_auth_profile(
    payload: dict,
    engine: Engine = Depends(get_engine),
    _: dict = Depends(caller_identity),
) -> dict:
    required = {"profile_id", "kind"}
    if not required.issubset(payload):
        raise HTTPException(400, f"Missing fields: {required - set(payload)}")
    if payload["kind"] not in ("api_key", "session_login"):
        raise HTTPException(
            400,
            "v0 supports kind=api_key|session_login. OAuth + app_on_behalf in Vault Pack.",
        )
    if "secrets" not in payload:
        raise HTTPException(400, "secrets is required for Flow A profiles")
    result = await engine.vault.create_profile(payload)
    return {"profile": result, "next_action": "verified"}


@router.delete("/profiles/{profile_id}", status_code=204)
async def revoke_profile(
    profile_id: str,
    engine: Engine = Depends(get_engine),
    _: dict = Depends(caller_identity),
) -> None:
    await engine.vault.revoke_profile(profile_id)
