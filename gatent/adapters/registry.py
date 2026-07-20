"""AdapterRegistry — name -> class lookup for every axis.

Adapters self-register at import time via decorators.
"""
from __future__ import annotations

from gatent.adapters.base import (
    Extractor,
    Notifier,
    Runner,
    Sink,
    Transformer,
    Trigger,
)
from gatent.core.config_store_protocol import ConfigStore
from gatent.core.state_store_protocol import StateStore
from gatent.core.types import Module
from gatent.core.vault_protocol import Vault


class AdapterRegistry:
    """Single source of truth for which adapter implements which axis."""

    def __init__(self):
        self._runners: dict[str, type[Runner]] = {}
        self._sinks: dict[str, type[Sink]] = {}
        self._notifiers: dict[str, type[Notifier]] = {}
        self._extractors: dict[str, type[Extractor]] = {}
        self._transformers: dict[str, type[Transformer]] = {}
        self._triggers: dict[str, type[Trigger]] = {}
        self._config_stores: dict[str, type[ConfigStore]] = {}
        self._state_stores: dict[str, type[StateStore]] = {}
        self._vaults: dict[str, type[Vault]] = {}

    # ----- Registration decorators -----

    def runner(self, name: str):
        def deco(cls):
            self._runners[name] = cls
            return cls
        return deco

    def sink(self, name: str):
        def deco(cls):
            self._sinks[name] = cls
            return cls
        return deco

    def notifier(self, name: str):
        def deco(cls):
            self._notifiers[name] = cls
            return cls
        return deco

    def extractor(self, name: str):
        def deco(cls):
            self._extractors[name] = cls
            return cls
        return deco

    def transformer(self, name: str):
        def deco(cls):
            self._transformers[name] = cls
            return cls
        return deco

    def trigger(self, name: str):
        def deco(cls):
            self._triggers[name] = cls
            return cls
        return deco

    def config_store(self, name: str):
        def deco(cls):
            self._config_stores[name] = cls
            return cls
        return deco

    def state_store(self, name: str):
        def deco(cls):
            self._state_stores[name] = cls
            return cls
        return deco

    def vault(self, name: str):
        def deco(cls):
            self._vaults[name] = cls
            return cls
        return deco

    # ----- Resolution -----

    def resolve_runner(self, module: Module, profile_default: str) -> Runner:
        name = module.raw_config.get("runner", profile_default)
        if name not in self._runners:
            raise ValueError(f"Runner '{name}' not registered. Registered: {list(self._runners)}")
        return self._runners[name]()

    def resolve_extractor(self, name: str) -> Extractor:
        if name not in self._extractors:
            raise ValueError(f"Extractor '{name}' not registered.")
        return self._extractors[name]()

    def resolve_transformer(self, op_name: str) -> Transformer:
        if op_name not in self._transformers:
            raise ValueError(f"Transformer '{op_name}' not registered.")
        return self._transformers[op_name]()

    def resolve_sink(self, sink_config: dict) -> Sink:
        name = sink_config.get("type")
        if name not in self._sinks:
            raise ValueError(f"Sink '{name}' not registered.")
        return self._sinks[name]()

    def resolve_notifier(self, notifier_config: dict) -> Notifier:
        name = notifier_config.get("type")
        if name not in self._notifiers:
            raise ValueError(f"Notifier '{name}' not registered.")
        return self._notifiers[name]()

    def resolve_trigger(self, trigger_config: dict) -> Trigger:
        name = trigger_config.get("type")
        if name not in self._triggers:
            raise ValueError(f"Trigger '{name}' not registered.")
        return self._triggers[name]()


# Module-level singleton — adapters import this and register against it
registry = AdapterRegistry()
