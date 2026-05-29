from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

JsonObject = dict[str, Any]


class ApiSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TraceResponse(ApiSchema):
    trace_id: UUID
