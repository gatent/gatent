"""Cast string fields to typed values."""
from __future__ import annotations

from datetime import datetime

from gatent.adapters.base import Transformer
from gatent.adapters.registry import registry
from gatent.core.types import PipelineContext


@registry.transformer("cast")
class CastTransformer(Transformer):
    """Cast field values to specified types.

    op shape:
      operation: cast
      casts:
        priority: int
        active: bool
        due_date: datetime
    """

    async def apply(
        self, op: dict, records: list[dict], ctx: PipelineContext
    ) -> list[dict]:
        casts = op.get("casts", {})
        for rec in records:
            for field, target_type in casts.items():
                val = rec.get(field)
                if val is None:
                    continue
                rec[field] = self._cast(val, target_type)
        return records

    @staticmethod
    def _cast(val, target_type: str):
        if target_type == "int":
            try:
                return int(str(val).strip())
            except ValueError:
                return None
        if target_type == "float":
            try:
                return float(str(val).strip())
            except ValueError:
                return None
        if target_type == "bool":
            return str(val).strip().lower() in ("true", "1", "yes", "y")
        if target_type == "datetime":
            try:
                return datetime.fromisoformat(str(val).strip())
            except ValueError:
                return None
        if target_type == "str":
            return str(val)
        return val
