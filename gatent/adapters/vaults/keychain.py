"""Local OS keychain vault.

Stores credentials in macOS Keychain / GNOME Keyring / Windows Credential Manager.
Audit log written to disk at ~/.gatent/vault_audit.log.
NEVER logs decrypted credentials.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import keyring

from gatent.adapters.registry import registry
from gatent.core.types import AuthCredentials, Module, UserActionRequiredError

_SERVICE_PREFIX = "gatent.vault"
_AUDIT_LOG = Path("~/.gatent/vault_audit.log").expanduser()


@registry.vault("keychain")
class LocalKeychainVault:
    def __init__(self):
        _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)

    async def load_credentials(
        self, profile_id: str, module: Module
    ) -> AuthCredentials:
        self._audit("load", profile_id, module.module_id)
        raw = keyring.get_password(_SERVICE_PREFIX, profile_id)
        if raw is None:
            raise UserActionRequiredError(
                f"Auth profile '{profile_id}' not found in keychain.",
                remediation=f"Run `gatent auth setup {profile_id}` to add credentials.",
            )
        data = json.loads(raw)
        return AuthCredentials(
            profile_id=profile_id,
            kind=data["kind"],
            secrets=data["secrets"],
            metadata=data.get("metadata", {}),
        )

    async def create_profile(self, profile_data: dict) -> dict:
        profile_id = profile_data["profile_id"]
        kind = profile_data["kind"]
        secrets = profile_data["secrets"]
        metadata = profile_data.get("metadata", {})
        keyring.set_password(
            _SERVICE_PREFIX, profile_id,
            json.dumps({"kind": kind, "secrets": secrets, "metadata": metadata}),
        )
        self._audit("create", profile_id, None)
        return {"profile_id": profile_id, "kind": kind, "metadata": metadata}

    async def revoke_profile(self, profile_id: str) -> None:
        self._audit("revoke", profile_id, None)
        try:
            keyring.delete_password(_SERVICE_PREFIX, profile_id)
        except keyring.errors.PasswordDeleteError:
            pass

    async def refresh_profile(self, profile_id: str) -> None:
        # Local keychain has no built-in OAuth refresh; the caller must update
        # the profile via create_profile with new credentials.
        self._audit("refresh_attempted", profile_id, None)
        raise NotImplementedError(
            "Local keychain vault does not support OAuth refresh. "
            "Re-create the profile with fresh credentials."
        )

    @staticmethod
    def _audit(action: str, profile_id: str, module_id: Optional[str]) -> None:
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "profile_id": profile_id,
            "module_id": module_id,
        })
        with _AUDIT_LOG.open("a") as f:
            f.write(line + "\n")
