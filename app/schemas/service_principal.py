"""Service principal API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

class ServicePrincipalCreate(BaseModel):
    """Create service principal request."""

    name: str = Field(..., min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None

class ServicePrincipalResponse(BaseModel):
    """Service principal response without secret material."""

    id: UUID
    tenant_id: UUID
    name: str
    key_prefix: str
    key_fingerprint: str
    scopes: list[str]
    status: str
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None

    model_config = {"from_attributes": True}

class ServicePrincipalCreateResponse(ServicePrincipalResponse):
    """Create response that exposes the raw key once."""

    api_key: str

class ServicePrincipalCredential(BaseModel):
    """Tenant-scoped service-principal credential payload."""

    tenant_id: UUID
    api_key: str

class ServicePrincipalAuthResult(BaseModel):
    """Authenticated service principal context."""

    id: UUID
    tenant_id: UUID
    scopes: list[str]
    key_fingerprint: str
