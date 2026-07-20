"""Notion-as-config store — cloud / power-user equivalent of YamlFilesConfigStore.

Each module is a page in a Notion "Modules" database. Metadata lives in
properties; the full module config is a JSON string in the `Config` rich_text
property. (Configs beyond Notion's per-property text limit are a follow-up:
spill to the page body as a code block.)

Modules DB property schema:
  Module ID (title) | Title (rich_text) | Description (rich_text) |
  Tags (multi_select) | Auth Profile (rich_text) | Schema Ver (number) |
  Module Ver (rich_text) | Config (rich_text, JSON)

Connection: NOTION_TOKEN + GATENT_MODULES_DB from env.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from notion_client import AsyncClient

from gatent.adapters.registry import registry
from gatent.core.types import Module


@registry.config_store("notion")
class NotionConfigStore:
    def __init__(self, token: Optional[str] = None, database_id: Optional[str] = None):
        self._db = database_id or os.environ["GATENT_MODULES_DB"]
        self._notion = AsyncClient(auth=token or os.environ["NOTION_TOKEN"])

    async def load(self, module_id: str) -> Module:
        res = await self._notion.databases.query(
            database_id=self._db,
            filter={"property": "Module ID", "title": {"equals": module_id}},
            page_size=1,
        )
        results = res.get("results", [])
        if not results:
            raise FileNotFoundError(f"Module '{module_id}' not found in Notion DB {self._db}")
        return self._page_to_module(results[0])

    async def list_modules(self, tag: Optional[str] = None) -> list[Module]:
        filter_ = {"property": "Tags", "multi_select": {"contains": tag}} if tag else None
        modules: list[Module] = []
        cursor: Optional[str] = None
        while True:
            res = await self._notion.databases.query(
                database_id=self._db, filter=filter_, start_cursor=cursor, page_size=100,
            )
            for page in res.get("results", []):
                try:
                    modules.append(self._page_to_module(page))
                except Exception:
                    continue  # malformed page; skip
            if not res.get("has_more"):
                break
            cursor = res.get("next_cursor")
        return modules

    async def save(self, module: Module) -> None:
        props = self._module_to_props(module)
        existing = await self._notion.databases.query(
            database_id=self._db,
            filter={"property": "Module ID", "title": {"equals": module.module_id}},
            page_size=1,
        )
        results = existing.get("results", [])
        if results:
            await self._notion.pages.update(page_id=results[0]["id"], properties=props)
        else:
            await self._notion.pages.create(parent={"database_id": self._db}, properties=props)

    async def delete(self, module_id: str) -> None:
        existing = await self._notion.databases.query(
            database_id=self._db,
            filter={"property": "Module ID", "title": {"equals": module_id}},
            page_size=1,
        )
        for page in existing.get("results", []):
            await self._notion.pages.update(page_id=page["id"], archived=True)

    # ----- helpers -----
    def _page_to_module(self, page: dict) -> Module:
        p = page["properties"]
        raw_json = self._rich_text(p.get("Config"))
        raw_config = json.loads(raw_json) if raw_json else {}
        return Module(
            module_id=self._title(p.get("Module ID")),
            schema_version=self._number(p.get("Schema Ver")) or 0,
            module_version=self._rich_text(p.get("Module Ver")) or "0.1.0",
            title=self._rich_text(p.get("Title")) or self._title(p.get("Module ID")),
            description=self._rich_text(p.get("Description")) or "",
            tags=self._multi_select(p.get("Tags")),
            raw_config=raw_config,
            auth_profile_id=self._rich_text(p.get("Auth Profile")) or None,
        )

    def _module_to_props(self, module: Module) -> dict:
        return {
            "Module ID": {"title": [{"text": {"content": module.module_id}}]},
            "Title": self._rt(module.title),
            "Description": self._rt(module.description),
            "Tags": {"multi_select": [{"name": t} for t in module.tags]},
            "Auth Profile": self._rt(module.auth_profile_id or ""),
            "Schema Ver": {"number": module.schema_version},
            "Module Ver": self._rt(module.module_version),
            "Config": self._rt(json.dumps(module.raw_config)),
        }

    @staticmethod
    def _rt(value: str) -> dict:
        return {"rich_text": [{"text": {"content": value or ""}}]}

    @staticmethod
    def _title(prop: Optional[dict]) -> str:
        if not prop or not prop.get("title"):
            return ""
        return "".join(t.get("plain_text", "") for t in prop["title"])

    @staticmethod
    def _rich_text(prop: Optional[dict]) -> str:
        if not prop or not prop.get("rich_text"):
            return ""
        return "".join(t.get("plain_text", "") for t in prop["rich_text"])

    @staticmethod
    def _multi_select(prop: Optional[dict]) -> list:
        if not prop or not prop.get("multi_select"):
            return []
        return [o["name"] for o in prop["multi_select"]]

    @staticmethod
    def _number(prop: Optional[dict]):
        return prop.get("number") if prop else None
