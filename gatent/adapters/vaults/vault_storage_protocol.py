"""VaultStorage Protocol - where ciphertext + metadata persist.

Separate from StateStore because credential persistence has stricter durability
and audit requirements. Implementations: PostgresVaultStorage, SqliteVaultStorage
(later), InMemoryVaultStorage (test).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class VaultStorage(Protocol):
    async def write_profile(
        self,
        profile_id: str,
        kind: str,
        wrapped_secret_json: str,
        metadata_json: str,
    ) -> None: ...

    async def read_profile(self, profile_id: str) -> Optional[dict]:
        """Returns {profile_id, kind, wrapped_secret_json, metadata_json,
        created_at, rotated_at, last_used_at} or None."""
        ...

    async def update_last_used(self, profile_id: str, when: datetime) -> None: ...

    async def update_rotated(
        self,
        profile_id: str,
        wrapped_secret_json: str,
        when: datetime,
    ) -> None: ...

    async def delete_profile(self, profile_id: str) -> None: ...

    async def list_profiles(self) -> list[dict]: ...
