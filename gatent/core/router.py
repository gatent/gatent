"""The Router — decides which sinks/notifiers each event flows to."""
from __future__ import annotations

from gatent.core.types import Event, RoutedEntry, Severity


class Router:
    """Applies route rules to events.

    Route config shape (in module YAML):
        route:
          - match: {type: "new_record"}
            severity: warning
            sinks: [primary_sink]
            notifiers: [user_phone]
            template: new_record_alert
            requires_approval: false
          - match: {type: "field_changed", changed_fields_include: ["status"]}
            severity: info
            sinks: [primary_sink]
    """

    def __init__(self, route_config: list[dict]):
        self.rules = route_config

    def route(self, events: list[Event]) -> list[RoutedEntry]:
        routed: list[RoutedEntry] = []
        for event in events:
            for rule in self.rules:
                if self._matches(rule.get("match", {}), event):
                    routed.append(RoutedEntry(
                        event=event,
                        sinks=rule.get("sinks", []),
                        notifiers=rule.get("notifiers", []),
                        severity=Severity(rule.get("severity", event.severity.value)),
                        template_name=rule.get("template"),
                        requires_approval=rule.get("requires_approval", False),
                    ))
                    break  # first matching rule wins
        return routed

    def _matches(self, match_spec: dict, event: Event) -> bool:
        if not match_spec:
            return True
        if "type" in match_spec and match_spec["type"] != event.type:
            return False
        if "changed_fields_include" in match_spec:
            if not event.changed_fields:
                return False
            required = set(match_spec["changed_fields_include"])
            if not required.issubset(set(event.changed_fields)):
                return False
        if "severity_at_least" in match_spec:
            order = [Severity.INFO, Severity.WARNING, Severity.ERROR, Severity.CRITICAL]
            min_sev = Severity(match_spec["severity_at_least"])
            if order.index(event.severity) < order.index(min_sev):
                return False
        return True
