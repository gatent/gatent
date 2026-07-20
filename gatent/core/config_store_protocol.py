"""ConfigStore Protocol — where module YAML lives."""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from gatent.core.types import Module


@runtime_checkable
class ConfigStore(Protocol):
    """Loads, lists, and persists modules.

    Implementations: NotionConfigStore (Morgan's profile), YamlFilesConfigStore
    (cloud-lite), DatabaseConfigStore (multi-tenant cloud).
    """

    async def load(self, module_id: str) -> Module: ...

    async def list_modules(self, tag: Optional[str] = None) -> list[Module]: ...

    async def save(self, module: Module) -> None: ...

    async def delete(self, module_id: str) -> None: ...
