"""Maps GatentError subclasses to HTTP status / MCP error / CLI exit codes."""
from __future__ import annotations

from typing import NamedTuple

from gatent.core.types import (
    AwaitingApproval,
    ErrorClass,
    GatentError,
    PermanentError,
    RunnerCapabilityError,
    SkipModule,
    TransientError,
    UserActionRequiredError,
)


class ErrorMapping(NamedTuple):
    http_status: int
    mcp_code: int
    cli_exit: int
    user_message: str
    remediation: str | None
    error_class: str


def map_error(exc: BaseException) -> ErrorMapping:
    if isinstance(exc, UserActionRequiredError):
        return ErrorMapping(409, -32001, 2, str(exc),
                            getattr(exc, "remediation", None),
                            ErrorClass.USER_ACTION_REQUIRED.value)
    if isinstance(exc, RunnerCapabilityError):
        return ErrorMapping(400, -32602, 1, str(exc),
                            "Configure a runner that supports the required step types.",
                            ErrorClass.PERMANENT.value)
    if isinstance(exc, PermanentError):
        return ErrorMapping(400, -32602, 1, str(exc), None,
                            ErrorClass.PERMANENT.value)
    if isinstance(exc, TransientError):
        return ErrorMapping(503, -32000, 3, str(exc),
                            "Retry shortly. If persistent, check the upstream service.",
                            ErrorClass.TRANSIENT.value)
    if isinstance(exc, SkipModule):
        return ErrorMapping(200, 0, 0, str(exc), None,
                            ErrorClass.PERMANENT.value)
    if isinstance(exc, AwaitingApproval):
        return ErrorMapping(202, 0, 0, "Run paused awaiting approval.",
                            "Approve via the notification channel.",
                            ErrorClass.USER_ACTION_REQUIRED.value)
    if isinstance(exc, GatentError):
        return ErrorMapping(500, -32603, 1, str(exc), None,
                            ErrorClass.INTERNAL.value)
    return ErrorMapping(500, -32603, 1,
                        f"{type(exc).__name__}: {exc}", None,
                        ErrorClass.INTERNAL.value)
