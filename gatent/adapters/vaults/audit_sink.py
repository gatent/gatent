"""Audit sink for vault operations.

Minimal v0 implementation per Vault Pack P1 wiring spec:
JsonLinesAuditSink(path=) appends one JSON object per line.
Full AuditSink protocol + additional sinks land with Vault Pack Part 2.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class AuditSink(Protocol):
    async def write(self, entry: dict) -> None: ...


class JsonLinesAuditSink:
    """Append-only JSON-lines audit log. One entry per line."""

    def __init__(self, path: str = "~/.gatent/vault_audit.jsonl"):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def write(self, entry: dict) -> None:
        line = json.dumps(entry, default=str)
        async with self._lock:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._append, line)

    def _append(self, line: str) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
