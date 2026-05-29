from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.persistence.models import Tenant

JsonObject = dict[str, object]


class UnsetValue:
    pass


UNSET = UnsetValue()


def tenant_snapshot(tenant: Tenant) -> JsonObject:
    return {
        "id": str(tenant.id),
        "slug": tenant.slug,
        "display_name": tenant.display_name,
        "status": tenant.status,
        "config": tenant.config,
        "config_version": tenant.config_version,
    }


class TenantRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        slug: str,
        display_name: str | None,
        config: JsonObject,
    ) -> Tenant:
        tenant = Tenant(
            id=uuid4(),
            slug=slug,
            display_name=display_name,
            config=config,
            config_version=1,
        )
        self.session.add(tenant)
        self.session.flush()
        self.session.refresh(tenant)
        return tenant

    def list(self) -> list[Tenant]:
        return list(self.session.scalars(select(Tenant).order_by(Tenant.slug)).all())

    def get(self, tenant_id: UUID) -> Tenant | None:
        return self.session.get(Tenant, tenant_id)

    def update_config(
        self,
        *,
        tenant_id: UUID,
        display_name: str | None | UnsetValue,
        config: JsonObject | UnsetValue,
    ) -> tuple[JsonObject, Tenant | None]:
        tenant = self.get(tenant_id)
        if tenant is None:
            return {}, None
        before = tenant_snapshot(tenant)
        did_update = False
        if not isinstance(display_name, UnsetValue):
            tenant.display_name = display_name
            did_update = True
        if not isinstance(config, UnsetValue):
            tenant.config = config
            did_update = True
        if did_update:
            tenant.config_version += 1
        self.session.flush()
        self.session.refresh(tenant)
        return before, tenant
