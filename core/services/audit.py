from typing import Any
from uuid import UUID

from core.persistence.repositories.audit_log import AuditLogRepository
from core.services.principals import AdminPrincipal
from core.services.redaction import redact_sensitive_value

JsonObject = dict[str, Any]


def redact_audit_value(value: object) -> object:
    return redact_sensitive_value(value)


class AuditService:
    def __init__(self, repository: AuditLogRepository) -> None:
        self.repository = repository

    def record(
        self,
        *,
        tenant_id: UUID | None,
        trace_id: UUID,
        principal: AdminPrincipal,
        action: str,
        resource_type: str,
        resource_id: str,
        before: object | None,
        after: object | None,
    ) -> None:
        redacted_before = redact_audit_value(before) if before is not None else None
        redacted_after = redact_audit_value(after) if after is not None else None
        self.repository.append(
            tenant_id=tenant_id,
            trace_id=trace_id,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before=redacted_before if isinstance(redacted_before, dict) else None,
            after=redacted_after if isinstance(redacted_after, dict) else None,
        )
