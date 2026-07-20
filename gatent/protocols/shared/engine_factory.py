"""Single source of truth for constructing an Engine.

REST, MCP, and CLI all build the same engine via build_engine().
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import gatent.adapters.all  # noqa: F401  side-effect: registers all adapters

from gatent.adapters.config_stores.yaml_files import YamlFilesConfigStore
from gatent.adapters.registry import registry
from gatent.adapters.state_stores.sqlite_store import SqliteStateStore
from gatent.adapters.vaults.keychain import LocalKeychainVault
from gatent.core import Engine, Profile

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore

_DEFAULT_CONFIG_PATH = Path("~/.gatent/config.toml").expanduser()


def build_engine(profile_name: Optional[str] = None) -> Engine:
    """Build an Engine for the named profile.

    Resolution: profile_name arg > GATENT_PROFILE env > config.toml default > solo_local
    """
    config = _load_config()
    name = (
        profile_name
        or os.environ.get("GATENT_PROFILE")
        or config.get("default_profile", "solo_local")
    )
    profile_cfg = config.get("profiles", {}).get(name, {})

    if name == "solo_local":
        return _build_solo_local(profile_cfg)

    if name == "cloud":
        return _build_cloud(profile_cfg)

    raise ValueError(
        f"Unknown profile '{name}'. Supported: solo_local, cloud."
    )


def _build_solo_local(cfg: dict) -> Engine:
    db_path = cfg.get("state_store_path", "~/.gatent/gatent.db")
    modules_dir = cfg.get("modules_dir", "~/.gatent/modules")
    profile = Profile(
        name="solo_local",
        default_runner="local_python",
        default_state_store="sqlite",
        default_config_store="yaml_files",
        default_vault="keychain",
    )
    return Engine(
        registry=registry,
        profile=profile,
        config_store=YamlFilesConfigStore(modules_dir),
        state_store=SqliteStateStore(db_path),
        vault=LocalKeychainVault(),
    )


def _build_cloud(cfg: dict) -> Engine:
    """Full cloud profile: Supabase state + Notion config + Playwright runner + CloudVault.

    All wiring is env-driven (Modal gatent-secrets):
      SUPABASE_URL, SUPABASE_KEY       -> SupabaseStateStore()
      NOTION_TOKEN, GATENT_MODULES_DB  -> NotionConfigStore()
      KMS_KEY_ID (KEK ARN), AWS_REGION,
        AWS_ACCESS_KEY_ID/SECRET       -> AwsKmsClient(...)
      VAULT_POSTGRES_DSN               -> PostgresVaultStorage(dsn)
    """
    import gatent.adapters.all_cloud  # noqa: F401  registers supabase + notion + cloud_vault + browser

    from gatent.adapters.config_stores.notion import NotionConfigStore
    from gatent.adapters.state_stores.supabase import SupabaseStateStore
    from gatent.adapters.vaults.audit_sink import JsonLinesAuditSink
    from gatent.adapters.vaults.cloud_vault import CloudVault
    from gatent.adapters.vaults.envelope import EnvelopeEncryption
    from gatent.adapters.vaults.kms_aws import AwsKmsClient
    from gatent.adapters.vaults.postgres_vault_storage import PostgresVaultStorage

    kms = AwsKmsClient(
        kek_arn=os.environ["KMS_KEY_ID"],
        region=os.environ.get("AWS_REGION"),
    )
    vault = CloudVault(
        envelope=EnvelopeEncryption(kms),
        storage=PostgresVaultStorage(dsn=os.environ["VAULT_POSTGRES_DSN"]),
        audit_sink=JsonLinesAuditSink(
            path=cfg.get("audit", {}).get("path", "/archive/vault_audit.jsonl"),
        ),
    )

    profile = Profile(
        name="cloud",
        default_runner="browser_playwright",
        default_state_store="supabase",
        default_config_store="notion",
        default_vault="cloud_vault",
    )
    return Engine(
        registry=registry,
        profile=profile,
        config_store=NotionConfigStore(),
        state_store=SupabaseStateStore(),
        vault=vault,
    )


def _load_config() -> dict:
    if not _DEFAULT_CONFIG_PATH.exists():
        return {}
    with _DEFAULT_CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)
