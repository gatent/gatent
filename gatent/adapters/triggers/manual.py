"""Manual trigger — fired by REST endpoint or CLI."""
from __future__ import annotations

from typing import Awaitable, Callable, Optional

from gatent.adapters.base import Trigger
from gatent.adapters.registry import registry


@registry.trigger("manual")
class ManualTrigger(Trigger):
    """No background loop. Just exposes a fire() that the REST/CLI surface calls."""

    def __init__(self, trigger_config: Optional[dict] = None):
        self._on_fire: Optional[Callable[[dict], Awaitable[None]]] = None
        self._config = trigger_config or {}

    async def start(self, on_fire: Callable[[dict], Awaitable[None]]) -> None:
        self._on_fire = on_fire

    async def stop(self) -> None:
        self._on_fire = None

    async def fire(self, payload: dict) -> None:
        if self._on_fire is None:
            raise RuntimeError("ManualTrigger not started")
        await self._on_fire({"type": "manual", **payload})
