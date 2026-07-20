"""Regex substitute transformer."""
from __future__ import annotations

import re

from gatent.adapters.base import Transformer
from gatent.adapters.registry import registry
from gatent.core.types import PipelineContext


@registry.transformer("regex_substitute")
class RegexTransformer(Transformer):
    r"""Substitute via regex on a named field.

    op shape:
      operation: regex_substitute
      field: title
      pattern: "^\\[(\\w+)\\]\\s+"
      replacement: ""
    """

    async def apply(
        self, op: dict, records: list[dict], ctx: PipelineContext
    ) -> list[dict]:
        field = op["field"]
        pattern = re.compile(op["pattern"])
        replacement = op.get("replacement", "")
        for rec in records:
            val = rec.get(field)
            if isinstance(val, str):
                rec[field] = pattern.sub(replacement, val)
        return records
