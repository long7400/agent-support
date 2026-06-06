"""Audit API schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

class AuditEventResponse(BaseModel):
    """Audit event response DTO."""

    id: UUID
    tenant_id: UUID
    actor_type: str
    actor_id: str
    action: str
    trace_id: UUID | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    metadata_json: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
