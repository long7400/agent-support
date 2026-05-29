from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.api.schemas.messages import Platform
from core.persistence.models import TenantPlatform

JsonObject = dict[str, object]


def platform_snapshot(platform: TenantPlatform) -> JsonObject:
    return {
        "id": str(platform.id),
        "tenant_id": str(platform.tenant_id),
        "platform": platform.platform,
        "external_workspace_id": platform.external_workspace_id,
        "external_channel_id": platform.external_channel_id,
        "status": platform.status,
        "config": platform.config,
    }


class TenantPlatformRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        tenant_id: UUID,
        platform: Platform,
        external_workspace_id: str,
        external_channel_id: str,
        config: JsonObject,
    ) -> TenantPlatform:
        row = TenantPlatform(
            id=uuid4(),
            tenant_id=tenant_id,
            platform=platform.value,
            external_workspace_id=external_workspace_id,
            external_channel_id=external_channel_id,
            status="active",
            config=config,
        )
        self.session.add(row)
        self.session.flush()
        self.session.refresh(row)
        return row

    def list_by_tenant(self, tenant_id: UUID) -> list[TenantPlatform]:
        statement = (
            select(TenantPlatform)
            .where(TenantPlatform.tenant_id == tenant_id)
            .order_by(TenantPlatform.platform, TenantPlatform.external_channel_id)
        )
        return list(self.session.scalars(statement).all())

    def resolve_active(
        self,
        *,
        platform: Platform,
        external_workspace_id: str,
        external_channel_id: str,
    ) -> TenantPlatform | None:
        statement = select(TenantPlatform).where(
            TenantPlatform.platform == platform.value,
            TenantPlatform.external_workspace_id == external_workspace_id,
            TenantPlatform.external_channel_id == external_channel_id,
            TenantPlatform.status == "active",
        )
        return self.session.scalars(statement).one_or_none()
