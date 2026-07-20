"""Per-stage timeout budget."""
from __future__ import annotations

DEFAULT_BUDGET = {
    "trigger_to_auth_ms":   1_000,
    "auth_ms":              3_000,
    "navigate_ms":         60_000,
    "extract_ms":           5_000,
    "transform_ms":         2_000,
    "diff_ms":              3_000,
    "route_ms":               500,
    "sink_ms_per_event":    5_000,
    "notify_ms_per_event":  2_000,
    "total_ms":           300_000,  # 5 min hard cap
}


def stage_budget(module_config: dict, stage: str) -> int:
    """Returns ms budget for a stage. Per-module override > default."""
    overrides = module_config.get("budget", {})
    return overrides.get(stage, DEFAULT_BUDGET[stage])
