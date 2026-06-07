"""Helpers to normalize harness state for deterministic replay comparison.

Strips timestamps, UUIDs, and other non-deterministic fields so that
replay runs with the same fixtures produce identical outputs.
"""

from __future__ import annotations

import re
from typing import Any

# Pattern to match UUID-like strings
_UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)

# Fields to exclude from comparison (non-deterministic)
_NON_DETERMINISTIC_FIELDS = {
    "trace_id",
    "agent_run_id",
    "started_at",
    "completed_at",
    "created_at",
    "latency_ms",
    "heartbeat_at",
    "run_after_ts",
}

# Keys to strip from result dicts
_RESULT_STRIP_KEYS = {"agent_run_id"}


def normalize_for_replay(data: dict[str, Any], strip_uuids: bool = True) -> dict[str, Any]:
    """Normalize a dict for deterministic comparison between replay runs.

    Args:
        data: Dict to normalize (e.g., HarnessResult).
        strip_uuids: If True, replaces UUIDs with a placeholder.

    Returns:
        New dict with non-deterministic fields removed.
    """
    normalized = {}
    for key, value in data.items():
        # Skip non-deterministic fields
        if key in _NON_DETERMINISTIC_FIELDS or key in _RESULT_STRIP_KEYS:
            continue

        # Recurse into nested dicts
        if isinstance(value, dict):
            normalized[key] = normalize_for_replay(value, strip_uuids)
        elif isinstance(value, list):
            normalized[key] = _normalize_list(value, strip_uuids)
        elif isinstance(value, str) and strip_uuids:
            # Replace UUIDs with placeholder
            normalized[key] = _UUID_PATTERN.sub("<UUID>", value)
        else:
            normalized[key] = value

    return normalized


def _normalize_list(items: list[Any], strip_uuids: bool) -> list[Any]:
    """Normalize a list of items for replay comparison."""
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append(normalize_for_replay(item, strip_uuids))
        elif isinstance(item, str) and strip_uuids:
            result.append(_UUID_PATTERN.sub("<UUID>", item))
        else:
            result.append(item)
    return result


def assert_replay_equal(
    run_a: dict[str, Any],
    run_b: dict[str, Any],
    message: str = "Replay runs differ",
) -> None:
    """Assert that two harness runs produce the same deterministic output.

    Args:
        run_a: First run result (HarnessResult dict).
        run_b: Second run result (HarnessResult dict).
        message: Error message prefix.

    Raises:
        AssertionError: If the normalized results differ.
    """
    a = normalize_for_replay(run_a)
    b = normalize_for_replay(run_b)
    assert a == b, f"{message}: normalized outputs differ"
