"""SQLite state store using aiosqlite.

Single file at the configured path. WAL mode for concurrent reads.
Schema migrates on connect.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from gatent.adapters.registry import registry
from gatent.core.types import (
    ErrorClass,
    Event,
    RunRecord,
    RunStatus,
    Severity,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    module_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL,
    trigger_json TEXT NOT NULL,
    stage_durations_json TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    error_class TEXT,
    events_emitted INTEGER NOT NULL DEFAULT 0,
    sinks_succeeded INTEGER NOT NULL DEFAULT 0,
    sinks_failed INTEGER NOT NULL DEFAULT 0,
    approval_request_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_module_started ON runs(module_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    module_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_json TEXT,
    changed_fields_json TEXT,
    severity TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_module_ts ON events(module_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);

CREATE TABLE IF NOT EXISTS diff_state (
    module_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_state (
    approval_request_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@registry.state_store("sqlite")
class SqliteStateStore:
    def __init__(self, path: str = "./gatent.db"):
        self.path = Path(path).expanduser().resolve()
        self._connected = False

    async def _ensure(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self.path)
        if not self._connected:
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA foreign_keys=ON;")
            await conn.executescript(_SCHEMA)
            await conn.commit()
            self._connected = True
        return conn

    async def write_run(self, record: RunRecord) -> None:
        conn = await self._ensure()
        try:
            await conn.execute(
                """
                INSERT INTO runs (run_id, module_id, started_at, ended_at, status,
                    trigger_json, stage_durations_json, error, error_class,
                    events_emitted, sinks_succeeded, sinks_failed, approval_request_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    ended_at=excluded.ended_at,
                    status=excluded.status,
                    stage_durations_json=excluded.stage_durations_json,
                    error=excluded.error,
                    error_class=excluded.error_class,
                    events_emitted=excluded.events_emitted,
                    sinks_succeeded=excluded.sinks_succeeded,
                    sinks_failed=excluded.sinks_failed,
                    approval_request_id=excluded.approval_request_id
                """,
                (
                    record.run_id,
                    record.module_id,
                    record.started_at.isoformat(),
                    record.ended_at.isoformat() if record.ended_at else None,
                    record.status.value,
                    json.dumps(record.trigger),
                    json.dumps(record.stage_durations_ms),
                    record.error,
                    record.error_class.value if record.error_class else None,
                    record.events_emitted,
                    record.sinks_succeeded,
                    record.sinks_failed,
                    record.approval_request_id,
                ),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def read_run(self, run_id: str) -> Optional[RunRecord]:
        conn = await self._ensure()
        try:
            cursor = await conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            )
            row = await cursor.fetchone()
            return self._row_to_run(row) if row else None
        finally:
            await conn.close()

    async def list_runs(
        self,
        module_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[RunRecord]:
        conn = await self._ensure()
        try:
            sql = "SELECT * FROM runs WHERE 1=1"
            params: list = []
            if module_id:
                sql += " AND module_id = ?"
                params.append(module_id)
            if since:
                sql += " AND started_at >= ?"
                params.append(since.isoformat())
            sql += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [self._row_to_run(r) for r in rows]
        finally:
            await conn.close()

    async def write_events(self, events: list[Event]) -> None:
        if not events:
            return
        conn = await self._ensure()
        try:
            await conn.executemany(
                """
                INSERT INTO events (event_id, module_id, run_id, type, payload_json,
                    previous_json, changed_fields_json, severity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        e.event_id, e.module_id, e.run_id, e.type,
                        json.dumps(e.payload),
                        json.dumps(e.previous) if e.previous else None,
                        json.dumps(e.changed_fields) if e.changed_fields else None,
                        e.severity.value, e.timestamp.isoformat(),
                    )
                    for e in events
                ],
            )
            await conn.commit()
        finally:
            await conn.close()

    async def list_events(
        self,
        module_id: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[Event]:
        conn = await self._ensure()
        try:
            sql = "SELECT * FROM events WHERE 1=1"
            params: list = []
            if module_id:
                sql += " AND module_id = ?"
                params.append(module_id)
            if event_type:
                sql += " AND type = ?"
                params.append(event_type)
            if since:
                sql += " AND timestamp >= ?"
                params.append(since.isoformat())
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [self._row_to_event(r) for r in rows]
        finally:
            await conn.close()

    async def load_diff_state(self, module_id: str) -> dict:
        conn = await self._ensure()
        try:
            cursor = await conn.execute(
                "SELECT state_json FROM diff_state WHERE module_id = ?", (module_id,)
            )
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else {}
        finally:
            await conn.close()

    async def write_diff_state(self, module_id: str, state: dict) -> None:
        conn = await self._ensure()
        try:
            await conn.execute(
                """
                INSERT INTO diff_state (module_id, state_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(module_id) DO UPDATE SET
                    state_json=excluded.state_json,
                    updated_at=excluded.updated_at
                """,
                (module_id, json.dumps(state), datetime.now(timezone.utc).isoformat()),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def stash_approval_state(
        self, run_id: str, approval_request_id: str, ctx_snapshot: dict
    ) -> None:
        conn = await self._ensure()
        try:
            await conn.execute(
                """
                INSERT INTO approval_state (approval_request_id, run_id, snapshot_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    approval_request_id, run_id,
                    json.dumps(ctx_snapshot),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await conn.commit()
        finally:
            await conn.close()

    async def load_approval_state(self, approval_request_id: str) -> Optional[dict]:
        conn = await self._ensure()
        try:
            cursor = await conn.execute(
                "SELECT snapshot_json FROM approval_state WHERE approval_request_id = ?",
                (approval_request_id,),
            )
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None
        finally:
            await conn.close()

    # ----- helpers -----

    @staticmethod
    def _row_to_run(row) -> RunRecord:
        return RunRecord(
            run_id=row[0], module_id=row[1],
            started_at=datetime.fromisoformat(row[2]),
            ended_at=datetime.fromisoformat(row[3]) if row[3] else None,
            status=RunStatus(row[4]),
            trigger=json.loads(row[5]),
            stage_durations_ms=json.loads(row[6]),
            error=row[7],
            error_class=ErrorClass(row[8]) if row[8] else None,
            events_emitted=row[9],
            sinks_succeeded=row[10],
            sinks_failed=row[11],
            approval_request_id=row[12],
        )

    @staticmethod
    def _row_to_event(row) -> Event:
        return Event(
            event_id=row[0], module_id=row[1], run_id=row[2], type=row[3],
            payload=json.loads(row[4]),
            previous=json.loads(row[5]) if row[5] else None,
            changed_fields=json.loads(row[6]) if row[6] else None,
            severity=Severity(row[7]),
            timestamp=datetime.fromisoformat(row[8]),
        )
