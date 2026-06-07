"""Policy metadata for long-term memory retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryRetrievalPolicy:
    """Required policy context for tenant-scoped memory retrieval."""

    tenant_id: str
    user_id: str
    scope: str
    visibility: tuple[str, ...]

    @classmethod
    def from_context(
        cls,
        *,
        tenant_id: str | None,
        user_id: str | None,
        scope: str | None,
        visibility: list[str] | tuple[str, ...] | None = None,
    ) -> MemoryRetrievalPolicy | None:
        """Build a policy only when all fail-closed retrieval fields are present."""
        normalized_visibility = tuple(v for v in (visibility or ()) if v)
        if not tenant_id or not user_id or not scope or not normalized_visibility:
            return None
        return cls(tenant_id=str(tenant_id), user_id=str(user_id), scope=str(scope), visibility=normalized_visibility)


def memory_result_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Return the metadata payload used for policy filtering."""
    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return result


def memory_result_text(result: dict[str, Any]) -> str:
    """Extract display text without exposing backend-specific fields."""
    value = result.get("memory") or result.get("text") or result.get("content") or ""
    return str(value)


def memory_result_allowed(result: dict[str, Any], policy: MemoryRetrievalPolicy) -> bool:
    """Enforce tenant/user/scope/visibility/active filters before returning memory."""
    payload = memory_result_payload(result)
    return (
        str(payload.get("tenant_id", "")) == policy.tenant_id
        and str(payload.get("user_id", "")) == policy.user_id
        and str(payload.get("scope", "")) == policy.scope
        and str(payload.get("visibility", "")) in policy.visibility
        and payload.get("active", False) is True
    )
