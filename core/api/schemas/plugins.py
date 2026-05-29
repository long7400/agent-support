from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.services.redaction import redact_sensitive_value, secret_like_paths

JsonObject = dict[str, Any]


class TenantPluginUpdateRequest(BaseModel):
    config: JsonObject = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def reject_secret_like_config_keys(cls, value: JsonObject) -> JsonObject:
        secret_paths = secret_like_paths(value)
        if secret_paths:
            raise ValueError(
                "plugin config cannot include credential-like keys in this phase: "
                + ", ".join(secret_paths)
            )
        return value


class TenantPluginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    plugin_name: str
    enabled: bool
    config: JsonObject
    created_at: datetime
    updated_at: datetime


def tenant_plugin_response(plugin: object) -> TenantPluginResponse:
    response = TenantPluginResponse.model_validate(plugin)
    redacted_config = redact_sensitive_value(response.config)
    return response.model_copy(
        update={"config": redacted_config if isinstance(redacted_config, dict) else {}}
    )
