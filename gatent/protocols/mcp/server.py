"""MCP server: every Gatent module becomes an MCP tool.

Supports stdio (Claude Desktop, Cursor) and HTTP+SSE (remote agents).
Both transports use the same dynamic tool registration.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from gatent.core import Engine, Module
from gatent.protocols.shared.engine_factory import build_engine
from gatent.protocols.shared.error_mapping import map_error


class GatentMcpServer:
    """Wraps a Gatent Engine as an MCP server."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.server: Server = Server("gatent")
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            modules = await self.engine.config_store.list_modules()
            return [self._module_to_tool(m) for m in modules if self._is_exposed(m)]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            try:
                record = await self.engine.run_module(name, {
                    "type": "manual",
                    "source": "mcp",
                    **arguments,
                })
            except Exception as exc:
                m = map_error(exc)
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": {
                            "code": type(exc).__name__,
                            "message": m.user_message,
                            "class": m.error_class,
                            "remediation": m.remediation,
                        }
                    }),
                )]

            events_summary = await self._summarize_events(record.run_id)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "run_id": record.run_id,
                    "status": record.status.value,
                    "events_emitted": record.events_emitted,
                    "events": events_summary,
                    "duration_ms": sum(record.stage_durations_ms.values()),
                }),
            )]

    @staticmethod
    def _module_to_tool(module: Module) -> Tool:
        cfg = module.raw_config
        mcp_cfg = cfg.get("mcp", {})
        description = (
            mcp_cfg.get("description")
            or module.description
            or f"Run the {module.module_id} module."
        )
        input_schema = mcp_cfg.get("input_schema") or {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        }
        return Tool(
            name=module.module_id,
            description=description,
            inputSchema=input_schema,
        )

    @staticmethod
    def _is_exposed(module: Module) -> bool:
        return module.raw_config.get("mcp_exposed", True)

    async def _summarize_events(self, run_id: str) -> list[dict]:
        events = await self.engine.state_store.list_events(limit=20)
        return [
            {"type": e.type, "payload": e.payload, "severity": e.severity.value}
            for e in events if e.run_id == run_id
        ]

    async def run_stdio(self) -> None:
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream,
                self.server.create_initialization_options(),
            )


def main() -> None:
    engine = build_engine()
    server = GatentMcpServer(engine)
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
