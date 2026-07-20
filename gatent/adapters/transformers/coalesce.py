"""Fill missing fields with defaults."""
from __future__ import annotations

from gatent.adapters.base import Transformer
from gatent.adapters.registry import registry
from gatent.core.types import PipelineContext


@registry.transformer("coalesce")
class CoalesceTransformer(Transformer):
    """Fill missing or null fields with defaults.

    op shape:
      operation: coalesce
      defaults:
        priority: "normal"
        assignee: "unassigned"
    """

    async def apply(
        self, op: dict, records: list[dict], ctx: PipelineContext
    ) -> list[dict]:
        defaults = op.get("defaults", {})
        for rec in records:
            for key, default in defaults.items():
                if rec.get(key) in (None, ""):
                    rec[key] = default
        return records
