"""POST event to a webhook URL."""
from __future__ import annotations

import httpx

from gatent.adapters.base import Sink
from gatent.adapters.registry import registry
from gatent.core.types import Event, PipelineContext, SinkError


@registry.sink("webhook")
class WebhookSink(Sink):
    async def write(
        self, event: Event, sink_config: dict, ctx: PipelineContext
    ) -> None:
        url = sink_config["url"]
        headers = sink_config.get("headers", {})
        timeout = sink_config.get("timeout_seconds", 10)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=event.to_dict(), headers=headers)
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise SinkError(f"Webhook {url} returned {resp.status_code}")
                if resp.status_code >= 400:
                    raise SinkError(f"Webhook {url} returned {resp.status_code} (non-retryable)")
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            raise SinkError(f"Webhook {url} unreachable: {e}")
