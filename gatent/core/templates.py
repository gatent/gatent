"""Template rendering for notifier payloads.

Uses Jinja2 if installed; falls back to a tiny `{{ key }}` substituter so the
core has no hard dependency on Jinja for the simplest install profiles.
"""
from __future__ import annotations

import re
from typing import Any

try:
    from jinja2 import Environment, StrictUndefined
    _JINJA_AVAILABLE = True
    _env = Environment(undefined=StrictUndefined, autoescape=False)
except ImportError:
    _JINJA_AVAILABLE = False
    _env = None


_SIMPLE_VAR = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}")


def render_template(template: str, context: dict[str, Any]) -> str:
    """Render template with context.

    Supports Jinja2 syntax if installed, otherwise simple {{ key }} substitution
    (dotted access supported: {{ event.payload.title }}).
    """
    if _JINJA_AVAILABLE and _env is not None:
        return _env.from_string(template).render(**context)
    return _simple_render(template, context)


def _simple_render(template: str, context: dict[str, Any]) -> str:
    def sub(match: re.Match) -> str:
        path = match.group(1).split(".")
        value: Any = context
        for part in path:
            if isinstance(value, dict):
                value = value.get(part, "")
            else:
                value = getattr(value, part, "")
        return str(value)
    return _SIMPLE_VAR.sub(sub, template)


DEFAULT_TEMPLATE = "{{ event.type }}: {{ event.payload }}"
