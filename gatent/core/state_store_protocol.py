"""StateStore Protocol — the persistence boundary for run records, events, diff state."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from gatent.core.types import Event, RunRecord


@runtime_checkable
class StateStore(Protocol):
    """Persists run records, events, and per-module diff state.

    Implementations: SqliteStateStore (solo/local), PostgresStateStore (cloud).
    Adapters live in gatent/adapters/state_stores/.
    """

    async def write_run(self, record: RunRecord) -> None: ...

    async def read_run(self, run_id: str) -> Optional[RunRecord]: ...

    async def list_runs(
        self,
        module_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[RunRecord]: ...

    async def write_events(self, events: list[Event]) -> None: ...

    async def list_events(
        self,
        module_id: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[Event]: ...

    async def load_diff_state(self, module_id: str) -> dict:
        """Returns {identity_key_tuple: {field: value}}. Empty dict if first run."""
        ...

    async def write_diff_state(self, module_id: str, state: dict) -> None: ...

    async def stash_approval_state(
        self,
        run_id: str,
        approval_request_id: str,
        ctx_snapshot: dict,
    ) -> None: ...

    async def load_approval_state(self, approval_request_id: str) -> Optional[dict]: ...
