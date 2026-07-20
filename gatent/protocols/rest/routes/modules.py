"""Module CRUD + run."""
from __future__ import annotations

from typing import Optional

import yaml
from fastapi import APIRouter, Body, Depends, HTTPException, Request

from gatent.core import Engine, Module
from gatent.protocols.rest.dependencies import caller_identity, get_engine
from gatent.protocols.shared.error_mapping import map_error

router = APIRouter(tags=["modules"])


@router.get("/modules")
async def list_modules(
    tag: Optional[str] = None,
    limit: int = 50,
    engine: Engine = Depends(get_engine),
    _: dict = Depends(caller_identity),
) -> dict:
    modules = await engine.config_store.list_modules(tag=tag)
    return {
        "modules": [_module_to_dict(m) for m in modules[:limit]],
        "next_cursor": None,
    }


@router.post("/modules", status_code=201)
async def create_module(
    request: Request,
    engine: Engine = Depends(get_engine),
    _: dict = Depends(caller_identity),
) -> dict:
    raw = await _read_body(request)
    module_id = raw.get("module_id")
    if not module_id:
        raise HTTPException(400, "module_id is required")
    config = raw.get("config", raw)
    module = _build_module(module_id, config)
    await engine.config_store.save(module)
    return _module_to_dict(module)


@router.get("/modules/{module_id}")
async def get_module(
    module_id: str,
    engine: Engine = Depends(get_engine),
    _: dict = Depends(caller_identity),
) -> dict:
    try:
        module = await engine.config_store.load(module_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Module '{module_id}' not found")
    return _module_to_dict(module)


@router.put("/modules/{module_id}")
async def update_module(
    module_id: str,
    request: Request,
    engine: Engine = Depends(get_engine),
    _: dict = Depends(caller_identity),
) -> dict:
    raw = await _read_body(request)
    config = raw.get("config", raw)
    module = _build_module(module_id, config)
    await engine.config_store.save(module)
    return _module_to_dict(module)


@router.delete("/modules/{module_id}", status_code=204)
async def delete_module(
    module_id: str,
    engine: Engine = Depends(get_engine),
    _: dict = Depends(caller_identity),
) -> None:
    await engine.config_store.delete(module_id)


@router.post("/modules/{module_id}/run", status_code=202)
async def run_module(
    module_id: str,
    payload: Optional[dict] = Body(default=None),
    engine: Engine = Depends(get_engine),
    _: dict = Depends(caller_identity),
) -> dict:
    try:
        record = await engine.run_module(module_id, payload or {"type": "manual"})
    except Exception as exc:
        m = map_error(exc)
        raise HTTPException(
            status_code=m.http_status,
            detail={
                "code": type(exc).__name__,
                "message": m.user_message,
                "class": m.error_class,
                "remediation": m.remediation,
            },
        )
    return record.to_dict()


async def _read_body(request: Request) -> dict:
    content_type = request.headers.get("content-type", "application/json")
    if "yaml" in content_type:
        body = await request.body()
        return yaml.safe_load(body)
    return await request.json()


def _build_module(module_id: str, config: dict) -> Module:
    return Module(
        module_id=module_id,
        schema_version=config.get("schema_version", 0),
        module_version=config.get("module_version", "0.1.0"),
        title=config.get("title", module_id),
        description=config.get("description", ""),
        tags=config.get("tags", []),
        raw_config=config,
        auth_profile_id=config.get("auth_profile_id"),
    )


def _module_to_dict(m: Module) -> dict:
    return {
        "module_id": m.module_id,
        "schema_version": m.schema_version,
        "module_version": m.module_version,
        "title": m.title,
        "description": m.description,
        "tags": m.tags,
        "config": m.raw_config,
        "auth_profile_id": m.auth_profile_id,
    }
