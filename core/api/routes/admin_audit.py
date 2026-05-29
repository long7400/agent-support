from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.api.dependencies import get_admin_session, require_admin_principal
from core.api.schemas.audit import AuditLogResponse
from core.persistence.repositories.audit_log import AuditLogRepository
from core.services.principals import AdminPrincipal

router = APIRouter(prefix="/admin/audit-log", tags=["admin-audit"])

AdminDep = Annotated[AdminPrincipal, Depends(require_admin_principal)]
SessionDep = Annotated[Session, Depends(get_admin_session)]
LimitQuery = Annotated[int, Query(ge=1, le=500)]


@router.get("", response_model=list[AuditLogResponse])
def list_audit_log(
    principal: AdminDep,
    session: SessionDep,
    tenant_id: UUID | None = None,
    limit: LimitQuery = 100,
) -> list[AuditLogResponse]:
    del principal
    return [
        AuditLogResponse.model_validate(row)
        for row in AuditLogRepository(session).list(tenant_id=tenant_id, limit=limit)
    ]
