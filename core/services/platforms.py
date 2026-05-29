from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from core.api.schemas.messages import Platform
from core.persistence.repositories.tenant_platforms import TenantPlatformRepository
from core.services.errors import ServiceError
from core.services.redaction import secret_like_paths

JsonObject = dict[str, object]


class TenantPlatformRepositoryProtocol(Protocol):
    def create(
        self,
        *,
        tenant_id: UUID,
        platform: Platform,
        external_workspace_id: str,
        external_channel_id: str,
        config: JsonObject,
    ) -> Any: ...

    def resolve_active(
        self,
        *,
        platform: Platform,
        external_workspace_id: str,
        external_channel_id: str,
    ) -> Any | None: ...


class TenantPlatformService:
    def __init__(self, repository: TenantPlatformRepositoryProtocol) -> None:
        self.repository = repository

    @classmethod
    def from_session(cls, session: Any) -> TenantPlatformService:
        return cls(TenantPlatformRepository(session))

    def register_platform(
        self,
        *,
        tenant_id: UUID,
        platform: Platform,
        external_workspace_id: str,
        external_channel_id: str,
        config: JsonObject,
    ) -> Any:
        secret_paths = secret_like_paths(config)
        if secret_paths:
            raise ServiceError(
                code="TENANT_PLATFORM_CONFIG_REJECTED",
                message="Tenant platform config cannot include credential-like keys",
                status_code=422,
            )
        try:
            return self.repository.create(
                tenant_id=tenant_id,
                platform=platform,
                external_workspace_id=external_workspace_id,
                external_channel_id=external_channel_id,
                config=config,
            )
        except IntegrityError as exc:
            raise ServiceError(
                code="TENANT_PLATFORM_CONFLICT",
                message="Platform identity is already registered",
                status_code=409,
            ) from exc

    def resolve_active(
        self,
        *,
        platform: Platform,
        external_workspace_id: str,
        external_channel_id: str,
    ) -> Any:
        row = self.repository.resolve_active(
            platform=platform,
            external_workspace_id=external_workspace_id,
            external_channel_id=external_channel_id,
        )
        if row is None:
            raise ServiceError(
                code="TENANT_PLATFORM_NOT_FOUND",
                message="Tenant platform mapping not found",
                status_code=404,
            )
        return row
