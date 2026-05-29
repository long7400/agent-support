from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

JsonObject = dict[str, Any]
TenantStatus = Literal["active", "disabled"]


class TenantConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona: str | None = None
    model_provider: str | None = None
    model_name: str | None = None


class TenantCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    display_name: str | None = Field(default=None, max_length=255)
    config: TenantConfig = Field(default_factory=TenantConfig)


class TenantUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    config: TenantConfig | None = None

    @model_validator(mode="after")
    def reject_empty_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("tenant update must include at least one field")
        return self


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    display_name: str | None
    status: TenantStatus
    config: JsonObject
    config_version: int
    created_at: datetime
    updated_at: datetime
