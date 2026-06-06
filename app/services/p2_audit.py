"""P2 audit helper for platform ingest events.

Creates audit events for security-relevant platform ingest operations.
All fail-closed paths and successful ingest events are audited.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

# Import related models so SQLAlchemy's string relationships are registered
# before AuditEvent instances trigger mapper configuration in worker/API paths.
import app.models.service_principal  # noqa: F401
import app.models.tenant  # noqa: F401
from app.models.audit import AuditEvent


class P2Actor:
    """Actor context for P2 audit events."""

    def __init__(self, actor_type: str, actor_id: str):
        """Initialize actor with type and identifier."""
        self.actor_type = actor_type
        self.actor_id = actor_id


# Pre-defined actor types for P2
WEBHOOK_ACTOR = P2Actor("webhook", "telegram")
ADAPTER_ACTOR = P2Actor("adapter", "generic")
SYSTEM_ACTOR = P2Actor("system", "platform_ingest")


async def emit_audit_event(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    actor: P2Actor,
    action: str,
    metadata: dict[str, Any] | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    trace_id: UUID | None = None,
) -> AuditEvent:
    """Emit a P2 audit event.

    Args:
        session: Database session
        tenant_id: Tenant scope for the event
        actor: Who performed the action (webhook, adapter, system)
        action: What happened (e.g., webhook_secret_rejected)
        metadata: Additional context (must NOT contain secrets)
        before: State before the action (if applicable)
        after: State after the action (if applicable)
        trace_id: Optional correlation ID for tracing

    Returns:
        The created AuditEvent
    """
    event = AuditEvent(
        id=uuid4(),
        tenant_id=tenant_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action=action,
        before=before,
        after=after,
        metadata_json=metadata or {},
        trace_id=trace_id,
    )
    session.add(event)
    return event


def redact_for_audit(data: dict[str, Any], sensitive_keys: list[str] | None = None) -> dict[str, Any]:
    """Redact sensitive fields from a dictionary for audit logging.

    Args:
        data: Dictionary to redact
        sensitive_keys: Keys to redact (default: common secret fields)

    Returns:
        Redacted copy of the dictionary
    """
    if sensitive_keys is None:
        sensitive_keys = [
            "secret",
            "token",
            "credential",
            "password",
            "api_key",
            "webhook_secret",
            "bot_token",
        ]

    redacted = {}
    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_for_audit(value, sensitive_keys)
        else:
            redacted[key] = value

    return redacted
