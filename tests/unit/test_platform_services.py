from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from core.api.schemas.messages import Platform
from core.services.errors import ServiceError
from core.services.platforms import TenantPlatformService


class FakeTenantPlatformRepository:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.resolved: dict[tuple[Platform, str, str], dict[str, object]] = {}
        self.raise_integrity = False

    def create(
        self,
        *,
        tenant_id: object,
        platform: Platform,
        external_workspace_id: str,
        external_channel_id: str,
        config: dict[str, object],
    ) -> dict[str, object]:
        if self.raise_integrity:
            raise IntegrityError("insert", {}, Exception("duplicate"))
        platform_row = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            "platform": platform.value,
            "external_workspace_id": external_workspace_id,
            "external_channel_id": external_channel_id,
            "status": "active",
            "config": config,
        }
        self.created.append(platform_row)
        return platform_row

    def resolve_active(
        self,
        *,
        platform: Platform,
        external_workspace_id: str,
        external_channel_id: str,
    ) -> dict[str, object] | None:
        return self.resolved.get((platform, external_workspace_id, external_channel_id))


def test_platform_service_rejects_secret_like_config_before_persistence() -> None:
    repository = FakeTenantPlatformRepository()
    service = TenantPlatformService(repository)

    with pytest.raises(ServiceError) as exc_info:
        service.register_platform(
            tenant_id=uuid4(),
            platform=Platform.TELEGRAM,
            external_workspace_id="workspace-a",
            external_channel_id="channel-a",
            config={"bot_token": "demo-placeholder"},
        )

    assert exc_info.value.code == "TENANT_PLATFORM_CONFIG_REJECTED"
    assert repository.created == []


def test_platform_service_allows_adapter_credential_id_metadata() -> None:
    repository = FakeTenantPlatformRepository()
    service = TenantPlatformService(repository)

    row = service.register_platform(
        tenant_id=uuid4(),
        platform=Platform.TELEGRAM,
        external_workspace_id="workspace-a",
        external_channel_id="channel-a",
        config={"adapter_credential_id": "local-telegram-sandbox"},
    )

    assert row["config"] == {"adapter_credential_id": "local-telegram-sandbox"}


def test_platform_service_rejects_secret_like_adapter_credential_id_value() -> None:
    repository = FakeTenantPlatformRepository()
    service = TenantPlatformService(repository)

    with pytest.raises(ServiceError) as exc_info:
        service.register_platform(
            tenant_id=uuid4(),
            platform=Platform.TELEGRAM,
            external_workspace_id="workspace-a",
            external_channel_id="channel-a",
            config={"adapter_credential_id": "token=raw-secret"},
        )

    assert exc_info.value.code == "TENANT_PLATFORM_CONFIG_REJECTED"
    assert repository.created == []


def test_platform_service_rejects_secret_equals_adapter_credential_id_value() -> None:
    repository = FakeTenantPlatformRepository()
    service = TenantPlatformService(repository)

    with pytest.raises(ServiceError) as exc_info:
        service.register_platform(
            tenant_id=uuid4(),
            platform=Platform.TELEGRAM,
            external_workspace_id="workspace-a",
            external_channel_id="channel-a",
            config={"adapter_credential_id": "secret=raw-secret"},
        )

    assert exc_info.value.code == "TENANT_PLATFORM_CONFIG_REJECTED"
    assert repository.created == []


def test_platform_service_maps_duplicate_platform_identity_to_conflict() -> None:
    repository = FakeTenantPlatformRepository()
    repository.raise_integrity = True
    service = TenantPlatformService(repository)

    with pytest.raises(ServiceError) as exc_info:
        service.register_platform(
            tenant_id=uuid4(),
            platform=Platform.DISCORD,
            external_workspace_id="workspace-a",
            external_channel_id="channel-a",
            config={},
        )

    assert exc_info.value.code == "TENANT_PLATFORM_CONFLICT"
    assert exc_info.value.status_code == 409


def test_platform_service_resolves_active_mapping() -> None:
    tenant_id = uuid4()
    repository = FakeTenantPlatformRepository()
    repository.resolved[(Platform.TELEGRAM, "workspace-a", "channel-a")] = {
        "id": uuid4(),
        "tenant_id": tenant_id,
        "platform": "telegram",
        "external_workspace_id": "workspace-a",
        "external_channel_id": "channel-a",
        "status": "active",
        "config": {},
    }
    service = TenantPlatformService(repository)

    platform_row = service.resolve_active(
        platform=Platform.TELEGRAM,
        external_workspace_id="workspace-a",
        external_channel_id="channel-a",
    )

    assert platform_row["tenant_id"] == tenant_id


def test_platform_service_missing_mapping_is_not_found() -> None:
    service = TenantPlatformService(FakeTenantPlatformRepository())

    with pytest.raises(ServiceError) as exc_info:
        service.resolve_active(
            platform=Platform.TELEGRAM,
            external_workspace_id="workspace-a",
            external_channel_id="channel-a",
        )

    assert exc_info.value.code == "TENANT_PLATFORM_NOT_FOUND"
    assert exc_info.value.status_code == 404
