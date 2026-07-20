"""Supabase (Postgres) state store — cloud equivalent of SqliteStateStore.

Same StateStore contract and the same logical schema (runs / events /
diff_state / approval_state), in Postgres instead of SQLite. JSON-shaped
columns are JSONB.

Run-once Postgres schema (Supabase SQL editor):

    create table if not exists runs (
        run_id text primary key, module_id text not null,
        started_at timestamptz not null, ended_at timestamptz,
        status text not null, trigger jsonb not null default '{}',
        stage_durations jsonb not null default '{}', error text, error_class text,
        events_emitted int not null default 0, sinks_succeeded int not null default 0,
        sinks_failed int not null default 0, approval_request_id text);
    create index if not exists idx_runs_module_started on runs(module_id, started_at desc);
    create table if not exists events (
        event_id text primary key, module_id text not null, run_id text not null,
        type text not null, payload jsonb not null, previous jsonb,
        changed_fields jsonb, severity text not null, timestamp timestamptz not null);
    create index if not exists idx_events_module_ts on events(module_id, timestamp desc);
    create table if not exists diff_state (
        module_id text primary key, state jsonb not null, updated_at timestamptz not null);
    create table if not exists approval_state (
        approval_request_id text primary key, run_id text not null,
        snapshot jsonb not null, created_at timestamptz not null);

Connection: SUPABASE_URL + SUPABASE_KEY (service key) from env — matches the
Modal gatent-secrets in the Bootstrap Pack.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from supabase import AsyncClient, acreate_client

from gatent.adapters.registry import registry
from gatent.core.types import ErrorClass, Event, RunRecord, RunStatus, Severity


@registry.state_store("supabase")
class SupabaseStateStore:
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self._url = url or os.environ["SUPABASE_URL"]
        self._key = key or os.environ["SUPABASE_KEY"]
        self._client: Optional[AsyncClient] = None

    async def _c(self) -> AsyncClient:
        if self._client is None:
            self._client = await acreate_client(self._url, self._key)
        return self._client

    async def write_run(self, record: RunRecord) -> None:
        c = await self._c()
        await c.table("runs").upsert({
            "run_id": record.run_id,
            "module_id": record.module_id,
            "started_at": record.started_at.isoformat(),
            "ended_at": record.ended_at.isoformat() if record.ended_at else None,
            "status": record.status.value,
            "trigger": record.trigger,
            "stage_durations": record.stage_durations_ms,
            "error": record.error,
            "error_class": record.error_class.value if record.error_class else None,
            "events_emitted": record.events_emitted,
            "sinks_succeeded": record.sinks_succeeded,
            "sinks_failed": record.sinks_failed,
            "approval_request_id": record.approval_request_id,
        }, on_conflict="run_id").execute()

    async def read_run(self, run_id: str) -> Optional[RunRecord]:
        c = await self._c()
        res = await c.table("runs").select("*").eq("run_id", run_id).limit(1).execute()
        rows = res.data or []
        return self._to_run(rows[0]) if rows else None

    async def list_runs(self, module_id=None, since=None, limit=50) -> list[RunRecord]:
        c = await self._c()
        q = c.table("runs").select("*")
        if module_id:
            q = q.eq("module_id", module_id)
        if since:
            q = q.gte("started_at", since.isoformat())
        res = await q.order("started_at", desc=True).limit(limit).execute()
        return [self._to_run(r) for r in (res.data or [])]

    async def write_events(self, events: list[Event]) -> None:
        if not events:
            return
        c = await self._c()
        await c.table("events").insert([
            {
                "event_id": e.event_id, "module_id": e.module_id, "run_id": e.run_id,
                "type": e.type, "payload": e.payload, "previous": e.previous,
                "changed_fields": e.changed_fields, "severity": e.severity.value,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ]).execute()

    async def list_events(self, module_id=None, event_type=None, since=None, limit=100) -> list[Event]:
        c = await self._c()
        q = c.table("events").select("*")
        if module_id:
            q = q.eq("module_id", module_id)
        if event_type:
            q = q.eq("type", event_type)
        if since:
            q = q.gte("timestamp", since.isoformat())
        res = await q.order("timestamp", desc=True).limit(limit).execute()
        return [self._to_event(r) for r in (res.data or [])]

    async def load_diff_state(self, module_id: str) -> dict:
        c = await self._c()
        res = await c.table("diff_state").select("state").eq("module_id", module_id).limit(1).execute()
        rows = res.data or []
        return rows[0]["state"] if rows else {}

    async def write_diff_state(self, module_id: str, state: dict) -> None:
        c = await self._c()
        await c.table("diff_state").upsert({
            "module_id": module_id,
            "state": state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="module_id").execute()

    async def stash_approval_state(self, run_id, approval_request_id, ctx_snapshot) -> None:
        c = await self._c()
        await c.table("approval_state").upsert({
            "approval_request_id": approval_request_id,
            "run_id": run_id,
            "snapshot": ctx_snapshot,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="approval_request_id").execute()

    async def load_approval_state(self, approval_request_id: str) -> Optional[dict]:
        c = await self._c()
        res = await c.table("approval_state").select("snapshot").eq(
            "approval_request_id", approval_request_id).limit(1).execute()
        rows = res.data or []
        return rows[0]["snapshot"] if rows else None

    # ----- helpers: dict row -> typed -----
    @staticmethod
    def _to_run(r: dict) -> RunRecord:
        return RunRecord(
            run_id=r["run_id"], module_id=r["module_id"],
            started_at=datetime.fromisoformat(r["started_at"]),
            ended_at=datetime.fromisoformat(r["ended_at"]) if r.get("ended_at") else None,
            status=RunStatus(r["status"]),
            trigger=r.get("trigger") or {},
            stage_durations_ms=r.get("stage_durations") or {},
            error=r.get("error"),
            error_class=ErrorClass(r["error_class"]) if r.get("error_class") else None,
            events_emitted=r.get("events_emitted", 0),
            sinks_succeeded=r.get("sinks_succeeded", 0),
            sinks_failed=r.get("sinks_failed", 0),
            approval_request_id=r.get("approval_request_id"),
        )

    @staticmethod
    def _to_event(r: dict) -> Event:
        return Event(
            event_id=r["event_id"], module_id=r["module_id"], run_id=r["run_id"],
            type=r["type"], payload=r.get("payload") or {},
            previous=r.get("previous"), changed_fields=r.get("changed_fields"),
            severity=Severity(r["severity"]),
            timestamp=datetime.fromisoformat(r["timestamp"]),
        )
