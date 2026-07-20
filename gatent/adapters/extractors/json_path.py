"""JSONPath extractor for api_response."""
from __future__ import annotations

from jsonpath_ng import parse as parse_jsonpath

from gatent.adapters.base import Extractor
from gatent.adapters.registry import registry
from gatent.core.types import Module, PipelineContext, PermanentError


@registry.extractor("json_path")
class JsonPathExtractor(Extractor):
    """Extract records via JSONPath against api_response.

    Module config shape:
      extract:
        type: json_path
        rows_path: "$.data.items[*]"
        fields:
          id:    { path: "$.id" }
          title: { path: "$.attributes.title" }
          due:   { path: "$.attributes.due_date" }
    """

    async def extract(
        self, module: Module, ctx: PipelineContext
    ) -> list[dict]:
        cfg = module.config["extract"]
        if not ctx.navigation_result or ctx.navigation_result.api_response is None:
            raise PermanentError("JsonPathExtractor requires api_response in NavigationResult")
        rows_expr = parse_jsonpath(cfg["rows_path"])
        rows = [m.value for m in rows_expr.find(ctx.navigation_result.api_response)]
        field_exprs = {
            name: parse_jsonpath(spec["path"])
            for name, spec in cfg["fields"].items()
        }
        records = []
        for row in rows:
            rec = {}
            for name, expr in field_exprs.items():
                matches = expr.find(row)
                rec[name] = matches[0].value if matches else cfg["fields"][name].get("default")
            records.append(rec)
        return records
