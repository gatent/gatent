"""The Differ — identity-based incremental change detection."""
from __future__ import annotations

from typing import Iterable

from gatent.core.state_store_protocol import StateStore
from gatent.core.types import Event
from gatent.core.ulid_util import generate_ulid


class Differ:
    """Compares current extraction against last-seen state, emits Events.

    Identity is determined by `identity_fields`. Two records with the same
    identity tuple are considered the same record across runs.
    Content equality is determined by `content_fields` if specified, otherwise
    by full record equality minus `ignore_fields`.
    """

    def __init__(self, diff_config: dict, state_store: StateStore):
        self.identity_fields: list[str] = diff_config["identity_fields"]
        self.content_fields: list[str] = diff_config.get("content_fields", [])
        self.emit_on: set[str] = set(
            diff_config.get("emit_on", ["new_record", "field_changed"])
        )
        self.ignore_fields: set[str] = set(diff_config.get("ignore_fields", []))
        self.state = state_store

    async def compute(
        self,
        current_records: list[dict],
        module_id: str,
        run_id: str,
    ) -> list[Event]:
        prior = await self.state.load_diff_state(module_id)
        # prior shape: {identity_tuple_str: full_record_dict}

        events: list[Event] = []
        current_by_id = {self._identity_key(r): r for r in current_records}

        # New records
        new_ids = set(current_by_id) - set(prior)
        for nid in new_ids:
            if "new_record" in self.emit_on:
                events.append(Event.new_record(
                    event_id=generate_ulid(),
                    module_id=module_id,
                    run_id=run_id,
                    record=current_by_id[nid],
                ))

        # Deleted records
        deleted_ids = set(prior) - set(current_by_id)
        for did in deleted_ids:
            if "deleted" in self.emit_on:
                events.append(Event.deleted(
                    event_id=generate_ulid(),
                    module_id=module_id,
                    run_id=run_id,
                    record=prior[did],
                ))

        # Changed records
        for shared_id in set(prior) & set(current_by_id):
            old = prior[shared_id]
            new = current_by_id[shared_id]
            changed = self._changed_fields(old, new)
            if changed and "field_changed" in self.emit_on:
                events.append(Event.field_changed(
                    event_id=generate_ulid(),
                    module_id=module_id,
                    run_id=run_id,
                    new=new,
                    old=old,
                    fields=changed,
                ))

        # Persist new state
        new_state = {self._identity_key(r): r for r in current_records}
        await self.state.write_diff_state(module_id, new_state)
        return events

    def _identity_key(self, record: dict) -> str:
        """Stringify the identity tuple for use as a dict key."""
        return "|".join(str(record.get(f, "")) for f in self.identity_fields)

    def _changed_fields(self, old: dict, new: dict) -> list[str]:
        if self.content_fields:
            fields_to_check: Iterable[str] = self.content_fields
        else:
            fields_to_check = (set(old) | set(new)) - self.ignore_fields - set(self.identity_fields)
        return [f for f in fields_to_check if old.get(f) != new.get(f)]
