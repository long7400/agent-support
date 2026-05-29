from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.persistence.models import TenantPlugin

JsonObject = dict[str, object]


def plugin_snapshot(plugin: TenantPlugin) -> JsonObject:
    return {
        "id": str(plugin.id),
        "tenant_id": str(plugin.tenant_id),
        "plugin_name": plugin.plugin_name,
        "enabled": plugin.enabled,
        "config": plugin.config,
    }


class TenantPluginRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, *, tenant_id: UUID, plugin_name: str) -> TenantPlugin | None:
        statement = select(TenantPlugin).where(
            TenantPlugin.tenant_id == tenant_id,
            TenantPlugin.plugin_name == plugin_name,
        )
        return self.session.scalars(statement).one_or_none()

    def upsert_enabled(
        self,
        *,
        tenant_id: UUID,
        plugin_name: str,
        config: JsonObject,
    ) -> tuple[JsonObject | None, TenantPlugin]:
        plugin = self.get(tenant_id=tenant_id, plugin_name=plugin_name)
        before = plugin_snapshot(plugin) if plugin is not None else None
        statement = (
            pg_insert(TenantPlugin)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                plugin_name=plugin_name,
                enabled=True,
                config=config,
            )
            .on_conflict_do_update(
                index_elements=[TenantPlugin.tenant_id, TenantPlugin.plugin_name],
                set_={
                    "enabled": True,
                    "config": config,
                    "updated_at": func.now(),
                },
            )
            .returning(TenantPlugin.id)
        )
        plugin_id = self.session.execute(statement).scalar_one()
        plugin = self.session.get(TenantPlugin, plugin_id)
        if plugin is None:
            raise RuntimeError("tenant plugin upsert did not return a persisted row")
        self.session.refresh(plugin)
        return before, plugin

    def disable(
        self,
        *,
        tenant_id: UUID,
        plugin_name: str,
    ) -> tuple[JsonObject, TenantPlugin | None]:
        plugin = self.get(tenant_id=tenant_id, plugin_name=plugin_name)
        if plugin is None:
            return {}, None
        before = plugin_snapshot(plugin)
        plugin.enabled = False
        self.session.flush()
        self.session.refresh(plugin)
        return before, plugin
