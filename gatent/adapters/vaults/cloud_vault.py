"""CloudVault - the production-tier Vault adapter.

Uses envelope encryption (KMS-wrapped DEKs) for ciphertext at rest.
Registers as `cloud_vault` in the AdapterRegistry.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from gatent.adapters.registry import registry
from gatent.adapters.vaults.envelope import (
    EnvelopeEncryption,
    WrappedSecret,
)
from gatent.adapters.vaults.vault_storage_protocol import VaultStorage
from gatent.core.types import (
    AuthCredentials,
    Module,
    UserActionRequiredError,
)


@registry.vault("cloud_vault")
class CloudVault:
    """Production Vault: envelope encryption + KMS + persistent storage.

    Constructor takes injected dependencies so tests can swap in fakes:
        CloudVault(envelope, storage, audit_sink)
    """

    def __init__(
        self,
        envelope: EnvelopeEncryption | None = None,
        storage: VaultStorage | None = None,
        audit_sink=None,
    ):
        if envelope is None or storage is None:
            raise ValueError(
                "CloudVault requires envelope and storage to be wired by the "
                "profile factory. See gatent/protocols/shared/engine_factory.py "
                "for cloud profile assembly."
            )
        self.envelope = envelope
        self.storage = storage
        self.audit = audit_sink

    async def load_credentials(
        self, profile_id: str, module: Module
    ) -> AuthCredentials:
        record = await self.storage.read_profile(profile_id)
        if record is None:
            await self._audit("load_failed_not_found", profile_id, module.module_id)
            raise UserActionRequiredError(
                f"Auth profile '{profile_id}' not found.",
                remediation=f"Create via POST /v1/auth/profiles or `gatent auth setup {profile_id}`.",
            )
        wrapped = WrappedSecret.from_dict(json.loads(record["wrapped_secret_json"]))
        # Bind AAD to profile_id so substitution is detected.
        import base64
        expected_aad = base64.b64encode(
            self._aad_for(profile_id).encode("ascii")).decode("ascii")
        if wrapped.aad_b64 != expected_aad:
            await self._audit("load_failed_aad_mismatch", profile_id, module.module_id)
            raise PermissionError("Vault AAD mismatch - possible ciphertext tampering.")
        plaintext = await self.envelope.decrypt(wrapped)
        secrets = json.loads(plaintext.decode("utf-8"))
        metadata = json.loads(record["metadata_json"]) if record.get("metadata_json") else {}
        await self.storage.update_last_used(profile_id, datetime.now(timezone.utc))
        await self._audit("load", profile_id, module.module_id)
        return AuthCredentials(
            profile_id=profile_id,
            kind=record["kind"],
            secrets=secrets,
            metadata=metadata,
        )

    async def create_profile(self, profile_data: dict) -> dict:
        profile_id = profile_data["profile_id"]
        kind = profile_data["kind"]
        secrets = profile_data["secrets"]
        metadata = profile_data.get("metadata", {})

        plaintext = json.dumps(secrets).encode("utf-8")
        aad = self._aad_for(profile_id).encode("ascii")
        wrapped = await self.envelope.encrypt(plaintext, aad=aad)
        await self.storage.write_profile(
            profile_id=profile_id,
            kind=kind,
            wrapped_secret_json=json.dumps(wrapped.to_dict()),
            metadata_json=json.dumps(metadata),
        )
        await self._audit("create", profile_id, None)
        return {"profile_id": profile_id, "kind": kind, "metadata": metadata}

    async def revoke_profile(self, profile_id: str) -> None:
        await self.storage.delete_profile(profile_id)
        await self._audit("revoke", profile_id, None)

    async def refresh_profile(self, profile_id: str) -> None:
        """OAuth refresh lands with Vault Pack Part 2; api_key/session_login
        profiles require user action to refresh.
        """
        record = await self.storage.read_profile(profile_id)
        if record is None:
            raise UserActionRequiredError(
                f"Profile '{profile_id}' not found.",
                remediation="Re-create the profile.",
            )
        raise UserActionRequiredError(
            f"Profile '{profile_id}' has kind '{record['kind']}' which cannot "
            f"be auto-refreshed in v0.",
            remediation="Re-create the profile with new credentials. "
            "OAuth auto-refresh lands with Vault Pack Part 2.",
        )

    async def rewrap_after_kek_rotation(self) -> int:
        """Re-wrap every DEK with the current KEK. Returns count rotated.

        Run after rotating the KEK in KMS. Idempotent - profiles already on the
        current kek_id are skipped.
        """
        current_kek_id = self.envelope.kms.kek_id
        profiles = await self.storage.list_profiles()
        rotated = 0
        for profile in profiles:
            wrapped = WrappedSecret.from_dict(json.loads(profile["wrapped_secret_json"]))
            if wrapped.kek_id == current_kek_id:
                continue
            plaintext = await self.envelope.decrypt(wrapped)
            aad = self._aad_for(profile["profile_id"]).encode("ascii")
            new_wrapped = await self.envelope.encrypt(plaintext, aad=aad)
            await self.storage.update_rotated(
                profile_id=profile["profile_id"],
                wrapped_secret_json=json.dumps(new_wrapped.to_dict()),
                when=datetime.now(timezone.utc),
            )
            await self._audit("kek_rotation", profile["profile_id"], None)
            rotated += 1
        return rotated

    @staticmethod
    def _aad_for(profile_id: str) -> str:
        """AAD binds ciphertext to profile_id. Substitution attack defense."""
        return f"gatent.vault.profile:{profile_id}"

    async def _audit(self, action: str, profile_id: str, module_id: str | None) -> None:
        if self.audit is not None:
            await self.audit.write({
                "ts": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "profile_id": profile_id,
                "module_id": module_id,
            })
