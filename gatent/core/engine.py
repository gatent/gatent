"""The engine entrypoint: run_module."""
from __future__ import annotations

import traceback
from dataclasses import dataclass

from gatent.adapters.registry import AdapterRegistry
from gatent.core.config_store_protocol import ConfigStore
from gatent.core.pipeline import execute_pipeline
from gatent.core.state_store_protocol import StateStore
from gatent.core.types import (
    AwaitingApproval,
    ErrorClass,
    GatentError,
    PipelineContext,
    RunRecord,
    RunStatus,
    SkipModule,
)
from gatent.core.ulid_util import generate_ulid
from gatent.core.vault_protocol import Vault


@dataclass
class Profile:
    """Install profile — declares which adapters are defaults for this deployment."""
    name: str  # "solo_local" | "cloud_lite" | "power_user"
    default_runner: str
    default_state_store: str
    default_config_store: str
    default_vault: str


class Engine:
    """The Gatent engine. One instance per `gatent serve`."""

    def __init__(
        self,
        registry: AdapterRegistry,
        profile: Profile,
        config_store: ConfigStore,
        state_store: StateStore,
        vault: Vault,
    ):
        self.registry = registry
        self.profile = profile
        self.config_store = config_store
        self.state_store = state_store
        self.vault = vault

    async def run_module(self, module_id: str, trigger_payload: dict | None = None) -> RunRecord:
        run_id = generate_ulid()
        module = await self.config_store.load(module_id)
        record = RunRecord.start(run_id, module_id, trigger_payload or {"type": "manual"})
        await self.state_store.write_run(record)

        ctx = PipelineContext(
            module=module,
            run_id=run_id,
            trigger_payload=trigger_payload or {},
            engine=self,
        )

        try:
            await execute_pipeline(ctx, record)
            record.status = RunStatus.SUCCEEDED
        except SkipModule as e:
            record.status = RunStatus.SKIPPED
            record.error = str(e)
            record.error_class = ErrorClass.PERMANENT
        except AwaitingApproval as e:
            record.status = RunStatus.AWAITING_APPROVAL
            record.approval_request_id = e.routed_entry.event.event_id
            await self.state_store.stash_approval_state(
                run_id=run_id,
                approval_request_id=e.routed_entry.event.event_id,
                ctx_snapshot=_snapshot_ctx(ctx),
            )
        except GatentError as e:
            record.status = RunStatus.FAILED
            record.error = str(e)
            record.error_class = e.error_class
        except Exception as e:
            record.status = RunStatus.FAILED
            record.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            record.error_class = ErrorClass.INTERNAL
        finally:
            from datetime import datetime, timezone
            record.ended_at = datetime.now(timezone.utc)
            await self.state_store.write_run(record)

        return record


def _snapshot_ctx(ctx: PipelineContext) -> dict:
    """Snapshot pipeline context for AWAITING_APPROVAL resume.

    Excludes auth (never persisted in plaintext) and the engine reference.
    """
    return {
        "run_id": ctx.run_id,
        "trigger_payload": ctx.trigger_payload,
        "raw_records": ctx.raw_records,
        "events": [e.to_dict() for e in ctx.events],
        "routed_count": len(ctx.routed),
    }
