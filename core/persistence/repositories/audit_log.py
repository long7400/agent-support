from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.persistence.models import AuditLog

JsonObject = dict[str, object]


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(
        self,
        *,
        tenant_id: UUID | None,
        trace_id: UUID,
        actor_type: str,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        before: JsonObject | None,
        after: JsonObject | None,
    ) -> AuditLog:
        row = AuditLog(
            id=uuid4(),
            tenant_id=tenant_id,
            trace_id=trace_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before=before,
            after=after,
        )
        self.session.add(row)
        self.session.flush()
        self.session.refresh(row)
        return row

    def list(self, *, tenant_id: UUID | None = None, limit: int = 100) -> list[AuditLog]:
        statement = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if tenant_id is not None:
            statement = statement.where(AuditLog.tenant_id == tenant_id)
        return list(self.session.scalars(statement).all())
