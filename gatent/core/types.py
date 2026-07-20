"""Core dataclasses and enums for the Gatent engine.

All types are immutable-by-convention except RunRecord, which mutates as a run
progresses through the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ===== Status enums =====

class RunStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorClass(Enum):
    USER_ACTION_REQUIRED = "user_action_required"
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    INTERNAL = "internal"


# ===== Configuration =====

@dataclass(frozen=True)
class Module:
    """A loaded module: parsed YAML + metadata."""
    module_id: str
    schema_version: int
    module_version: str
    title: str
    description: str
    tags: list[str]
    raw_config: dict
    auth_profile_id: Optional[str] = None

    @property
    def config(self) -> dict:
        """Alias for raw_config (matches spec naming)."""
        return self.raw_config


@dataclass(frozen=True)
class AuthCredentials:
    """Decrypted credentials for a single run. NEVER persisted, NEVER logged."""
    profile_id: str
    kind: str  # "api_key" | "session_login" | "oauth" | "app_on_behalf"
    secrets: dict[str, str]
    metadata: dict[str, Any] = field(default_factory=dict)


# ===== Runtime state =====

@dataclass
class RunRecord:
    """Mutable state of a module run. Persisted at every stage transition."""
    run_id: str
    module_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: RunStatus = RunStatus.QUEUED
    trigger: dict = field(default_factory=dict)
    stage_durations_ms: dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None
    error_class: Optional[ErrorClass] = None
    events_emitted: int = 0
    sinks_succeeded: int = 0
    sinks_failed: int = 0
    approval_request_id: Optional[str] = None

    _stage_timers: dict[str, datetime] = field(default_factory=dict, repr=False)

    @classmethod
    def start(cls, run_id: str, module_id: str, trigger_payload: dict) -> "RunRecord":
        return cls(
            run_id=run_id,
            module_id=module_id,
            started_at=_now(),
            status=RunStatus.RUNNING,
            trigger=trigger_payload,
        )

    def stage_started(self, stage: str) -> None:
        self._stage_timers[stage] = _now()

    def stage_ended(self, stage: str) -> None:
        start = self._stage_timers.get(stage)
        if start is None:
            return
        elapsed_ms = int((_now() - start).total_seconds() * 1000)
        self.stage_durations_ms[stage] = elapsed_ms

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "module_id": self.module_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "status": self.status.value,
            "trigger": self.trigger,
            "stage_durations_ms": self.stage_durations_ms,
            "error": self.error,
            "error_class": self.error_class.value if self.error_class else None,
            "events_emitted": self.events_emitted,
            "sinks_succeeded": self.sinks_succeeded,
            "sinks_failed": self.sinks_failed,
            "approval_request_id": self.approval_request_id,
        }


# ===== Events =====

@dataclass(frozen=True)
class Event:
    """Something the differ noticed changed."""
    event_id: str
    module_id: str
    run_id: str
    type: str  # "new_record" | "field_changed" | "deleted" | custom
    payload: dict
    severity: Severity
    timestamp: datetime
    previous: Optional[dict] = None
    changed_fields: Optional[list[str]] = None

    @classmethod
    def new_record(cls, event_id: str, module_id: str, run_id: str, record: dict, severity: Severity = Severity.INFO) -> "Event":
        return cls(event_id, module_id, run_id, "new_record", record, severity, _now())

    @classmethod
    def field_changed(cls, event_id: str, module_id: str, run_id: str, new: dict, old: dict, fields: list[str], severity: Severity = Severity.INFO) -> "Event":
        return cls(event_id, module_id, run_id, "field_changed", new, severity, _now(), previous=old, changed_fields=fields)

    @classmethod
    def deleted(cls, event_id: str, module_id: str, run_id: str, record: dict, severity: Severity = Severity.INFO) -> "Event":
        return cls(event_id, module_id, run_id, "deleted", record, severity, _now())

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "module_id": self.module_id,
            "run_id": self.run_id,
            "type": self.type,
            "payload": self.payload,
            "previous": self.previous,
            "changed_fields": self.changed_fields,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
        }


# ===== Navigation =====

@dataclass
class NavigationResult:
    """Output of the Runner. Whatever shape extraction needs."""
    rendered_html: Optional[str] = None
    api_response: Optional[dict] = None
    final_url: Optional[str] = None
    cookies: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


# ===== Routing =====

@dataclass
class RoutedEntry:
    """Output of the Router: an event paired with its sinks/notifiers/severity."""
    event: Event
    sinks: list[str]
    notifiers: list[str]
    severity: Severity
    template_name: Optional[str] = None
    requires_approval: bool = False


# ===== Pipeline context (mutable scratchpad) =====

@dataclass
class PipelineContext:
    """Scratchpad passed through the 9-stage pipeline.

    Attributes are populated by each stage and read by subsequent stages.
    """
    module: Module
    run_id: str
    trigger_payload: dict
    engine: Any  # Forward-declared; Engine reference
    trigger: Optional[dict] = None
    auth: Optional[AuthCredentials] = None
    navigation_result: Optional[NavigationResult] = None
    raw_records: list[dict] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    routed: list[RoutedEntry] = field(default_factory=list)


# ===== Exceptions =====

class GatentError(Exception):
    """Base class for all engine errors."""
    error_class: ErrorClass = ErrorClass.INTERNAL


class SkipModule(GatentError):
    """Raised when a stage decides this run should end successfully-but-quiet.

    Examples: extract found zero records (no work to do), trigger payload
    indicates a no-op condition.
    """
    error_class = ErrorClass.PERMANENT


class AwaitingApproval(GatentError):
    """Raised when route emits a requires_approval entry.

    The engine catches this, stashes pipeline state, and transitions the run
    to AWAITING_APPROVAL. The approval callback resumes from notify stage.
    """
    error_class = ErrorClass.USER_ACTION_REQUIRED

    def __init__(self, routed_entry: RoutedEntry):
        super().__init__(f"Approval required for event {routed_entry.event.event_id}")
        self.routed_entry = routed_entry


class TransientError(GatentError):
    """Retryable. Connection errors, 5xx, 429s with Retry-After."""
    error_class = ErrorClass.TRANSIENT


class PermanentError(GatentError):
    """Not retryable. 4xx (except 429), parse failures, schema violations."""
    error_class = ErrorClass.PERMANENT


class UserActionRequiredError(GatentError):
    """User must do something before this can succeed.

    Examples: auth profile expired (re-auth), site requires CAPTCHA, MFA prompt.
    """
    error_class = ErrorClass.USER_ACTION_REQUIRED

    def __init__(self, message: str, remediation: str):
        super().__init__(message)
        self.remediation = remediation


class RunnerCapabilityError(PermanentError):
    """A navigate step used a capability the resolved runner doesn't support."""


class SinkError(GatentError):
    """Sink-specific failure. Logged + counted but doesn't fail the run."""
    error_class = ErrorClass.TRANSIENT


# ===== Helpers =====

def _now() -> datetime:
    return datetime.now(timezone.utc)
