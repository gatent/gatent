"""Append events to a .jsonl file."""
from __future__ import annotations

import json
from pathlib import Path

from gatent.adapters.base import Sink
from gatent.adapters.registry import registry
from gatent.core.types import Event, PipelineContext, SinkError


@registry.sink("json_lines")
class JsonLinesSink(Sink):
    async def write(
        self, event: Event, sink_config: dict, ctx: PipelineContext
    ) -> None:
        path = Path(sink_config.get("path", "./events.jsonl")).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except OSError as e:
            raise SinkError(f"Failed to write to {path}: {e}")
