"""Tenant control-plane API schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

class ActorContext(BaseModel):
    """Authenticated actor metadata for audit records."""

    actor_type: str = Field(..., max_length=64)
    actor_id: str = Field(..., max_length=128)

class TenantCreate(BaseModel):
    """Create tenant request."""

    slug: str = Field(..., min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    display_name: str = Field(..., min_length=1, max_length=200)
    retention_policy_json: dict[str, Any] = Field(default_factory=dict)

class TenantUpdate(BaseModel):
    """Update tenant metadata/status request."""

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, pattern=r"^(active|disabled|suspended|deleting)$")
    retention_policy_json: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=500)

class TenantResponse(BaseModel):
    """Tenant response DTO."""

    id: UUID
    slug: str
    display_name: str
    status: str
    config_version: int
    retention_policy_json: dict[str, Any]
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = {"from_attributes": True}

class TenantMemberCreate(BaseModel):
    """Create tenant membership request."""

    user_id: int
    role: str = Field(..., pattern=r"^(admin|moderator|viewer)$")

class TenantMembershipResponse(BaseModel):
    """Tenant membership response DTO."""

    id: UUID
    tenant_id: UUID
    user_id: int
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}

class TenantConfigUpdate(BaseModel):
    """Create a new tenant config version."""

    persona: dict[str, Any] = Field(default_factory=dict)
    official_links: list[dict[str, Any]] = Field(default_factory=list)
    moderation_mode: str = Field(default="shadow", pattern=r"^(shadow|propose|enforce)$")
    model_budget: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)

class TenantConfigVersionResponse(BaseModel):
    """Tenant config version response DTO."""

    id: UUID
    tenant_id: UUID
    version: int
    persona: dict[str, Any]
    official_links: list[dict[str, Any]]
    moderation_mode: str
    model_budget: dict[str, Any]
    created_by_actor_type: str
    created_by_actor_id: str
    reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
