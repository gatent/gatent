"""CSS-selector extractor: rendered_html -> list[dict]."""
from __future__ import annotations

from lxml import html as lxml_html

from gatent.adapters.base import Extractor
from gatent.adapters.registry import registry
from gatent.core.types import Module, PipelineContext, PermanentError


@registry.extractor("css")
class CssExtractor(Extractor):
    """Extracts records using CSS selectors.

    Module config shape:
      extract:
        type: css
        row_selector: "table.results tr.row"
        fields:
          title: { selector: "td.title", attr: "text" }
          url:   { selector: "a.title-link", attr: "href" }
          due:   { selector: "td.due", attr: "data-iso" }
    """

    async def extract(
        self, module: Module, ctx: PipelineContext
    ) -> list[dict]:
        cfg = module.config["extract"]
        if not ctx.navigation_result or not ctx.navigation_result.rendered_html:
            raise PermanentError("CssExtractor requires rendered_html in NavigationResult")
        doc = lxml_html.fromstring(ctx.navigation_result.rendered_html)
        rows = doc.cssselect(cfg["row_selector"])
        records = []
        for row in rows:
            record = {}
            for field_name, field_cfg in cfg["fields"].items():
                record[field_name] = self._extract_field(row, field_cfg)
            records.append(record)
        return records

    @staticmethod
    def _extract_field(row, field_cfg: dict):
        nodes = row.cssselect(field_cfg["selector"])
        if not nodes:
            return field_cfg.get("default")
        node = nodes[0]
        attr = field_cfg.get("attr", "text")
        if attr == "text":
            return (node.text_content() or "").strip()
        return node.get(attr)
