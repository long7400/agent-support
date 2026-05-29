from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

JsonObject = dict[str, Any]


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None
    trace_id: UUID
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    before: JsonObject | None
    after: JsonObject | None
    created_at: datetime
