"""Cron trigger using croniter."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from croniter import croniter

from gatent.adapters.base import Trigger
from gatent.adapters.registry import registry


@registry.trigger("cron")
class CronTrigger(Trigger):
    """Trigger config:
      type: cron
      schedule: "*/15 * * * *"
      module_id: my-watcher
    """

    def __init__(self, trigger_config: Optional[dict] = None):
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._config = trigger_config or {}

    async def start(self, on_fire: Callable[[dict], Awaitable[None]]) -> None:
        self._task = asyncio.create_task(self._loop(on_fire))

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task

    async def _loop(self, on_fire) -> None:
        schedule = self._config["schedule"]
        module_id = self._config["module_id"]
        cron = croniter(schedule, datetime.now(timezone.utc))
        while not self._stop_event.is_set():
            next_fire = cron.get_next(datetime)
            seconds_until = (next_fire - datetime.now(timezone.utc)).total_seconds()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=seconds_until)
                return  # stopped
            except asyncio.TimeoutError:
                pass  # time to fire
            await on_fire({
                "type": "cron",
                "module_id": module_id,
                "scheduled_for": next_fire.isoformat(),
            })
