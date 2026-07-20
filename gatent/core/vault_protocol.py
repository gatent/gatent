"""Vault Protocol — where credentials live."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from gatent.core.types import AuthCredentials, Module


@runtime_checkable
class Vault(Protocol):
    """Stores encrypted credentials; decrypts only into in-memory AuthCredentials.

    Implementations: KeychainVault (local), ModalSecretsVault (cloud), see Auth
    Vault Architecture v0 for full design.
    """

    async def load_credentials(
        self,
        profile_id: str,
        module: Module,
    ) -> AuthCredentials: ...

    async def create_profile(self, profile_data: dict) -> dict: ...

    async def revoke_profile(self, profile_id: str) -> None: ...

    async def refresh_profile(self, profile_id: str) -> None: ...
