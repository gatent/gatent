"""Abstract base classes for every adapter axis.

Adapters implement these. The engine consumes only these ABCs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from gatent.core.types import Event, Module, NavigationResult, PipelineContext


class Runner(ABC):
    """Executes the navigate stage."""

    @abstractmethod
    async def navigate(self, module: Module, ctx: PipelineContext) -> NavigationResult: ...

    @abstractmethod
    def supports(self, navigate_step: dict) -> bool: ...


class Extractor(ABC):
    """Pulls structured records out of a NavigationResult."""

    @abstractmethod
    async def extract(self, module: Module, ctx: PipelineContext) -> list[dict]: ...


class Transformer(ABC):
    """Applies a single transform op to the record list."""

    @abstractmethod
    async def apply(self, op: dict, records: list[dict], ctx: PipelineContext) -> list[dict]: ...


class Sink(ABC):
    """Writes an event to a destination (database, webhook, file, etc.)."""

    @abstractmethod
    async def write(self, event: Event, sink_config: dict, ctx: PipelineContext) -> None: ...


class Notifier(ABC):
    """Delivers a rendered message to a user surface (push, email, SMS, etc.)."""

    @abstractmethod
    async def send(self, message: str, severity: Any, notifier_config: dict) -> None: ...


class Trigger(ABC):
    """Fires module runs from external signals (cron, webhook, manual)."""

    @abstractmethod
    async def start(self, on_fire) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...
