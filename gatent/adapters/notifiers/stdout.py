"""Console notifier — useful for solo_local development."""
from __future__ import annotations

import sys

from gatent.adapters.base import Notifier
from gatent.adapters.registry import registry
from gatent.core.types import Severity


@registry.notifier("stdout")
class StdoutNotifier(Notifier):
    async def send(
        self, message: str, severity: Severity, notifier_config: dict
    ) -> None:
        prefix = {
            Severity.INFO: "[INFO]",
            Severity.WARNING: "[WARN]",
            Severity.ERROR: "[ERR ]",
            Severity.CRITICAL: "[CRIT]",
        }[severity]
        stream = sys.stderr if severity in (Severity.ERROR, Severity.CRITICAL) else sys.stdout
        print(f"{prefix} {message}", file=stream, flush=True)
