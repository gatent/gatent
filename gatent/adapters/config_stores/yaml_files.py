"""Filesystem config store: one YAML file per module."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from gatent.adapters.registry import registry
from gatent.core.types import Module


@registry.config_store("yaml_files")
class YamlFilesConfigStore:
    def __init__(self, modules_dir: str = "./modules"):
        self.modules_dir = Path(modules_dir).expanduser().resolve()
        self.modules_dir.mkdir(parents=True, exist_ok=True)

    async def load(self, module_id: str) -> Module:
        path = self.modules_dir / f"{module_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Module '{module_id}' not found at {path}")
        raw = yaml.safe_load(path.read_text())
        return self._parse(module_id, raw)

    async def list_modules(self, tag: Optional[str] = None) -> list[Module]:
        results = []
        for path in self.modules_dir.glob("*.yaml"):
            try:
                raw = yaml.safe_load(path.read_text())
                module = self._parse(path.stem, raw)
                if tag is None or tag in module.tags:
                    results.append(module)
            except Exception:
                continue  # malformed; skip
        return results

    async def save(self, module: Module) -> None:
        path = self.modules_dir / f"{module.module_id}.yaml"
        path.write_text(yaml.safe_dump(module.raw_config, sort_keys=False))

    async def delete(self, module_id: str) -> None:
        path = self.modules_dir / f"{module_id}.yaml"
        if path.exists():
            path.unlink()

    @staticmethod
    def _parse(module_id: str, raw: dict) -> Module:
        return Module(
            module_id=module_id,
            schema_version=raw.get("schema_version", 0),
            module_version=raw.get("module_version", "0.1.0"),
            title=raw.get("title", module_id),
            description=raw.get("description", ""),
            tags=raw.get("tags", []),
            raw_config=raw,
            auth_profile_id=raw.get("auth_profile_id"),
        )
