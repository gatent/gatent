"""ntfy.sh notifier — push notifications to phone."""
from __future__ import annotations

import httpx

from gatent.adapters.base import Notifier
from gatent.adapters.registry import registry
from gatent.core.types import Severity

_PRIORITY_MAP = {
    Severity.INFO: 3,
    Severity.WARNING: 4,
    Severity.ERROR: 5,
    Severity.CRITICAL: 5,
}


@registry.notifier("ntfy")
class NtfyNotifier(Notifier):
    """Notifier config:
      type: ntfy
      topic: morgan-gatent-alerts
      base_url: https://ntfy.sh   # optional
      title: "Gatent alert"        # optional
    """

    async def send(
        self, message: str, severity: Severity, notifier_config: dict
    ) -> None:
        topic = notifier_config["topic"]
        base = notifier_config.get("base_url", "https://ntfy.sh")
        url = f"{base}/{topic}"
        headers = {
            "Priority": str(_PRIORITY_MAP[severity]),
        }
        if "title" in notifier_config:
            headers["Title"] = notifier_config["title"]
        if severity == Severity.CRITICAL:
            headers["Tags"] = "rotating_light"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, headers=headers, content=message.encode("utf-8"))
