from enum import StrEnum

from core.api.schemas.messages import Platform


class StreamDirection(StrEnum):
    INGRESS = "ingress"
    OUTBOUND = "outbound"
    DLQ = "dlq"


def stream_name(
    *,
    environment: str,
    tenant_scope: str,
    direction: StreamDirection,
    platform: Platform,
) -> str:
    parts = {
        "environment": environment,
        "tenant_scope": tenant_scope,
        "direction": direction.value,
        "platform": platform.value,
    }
    for name, value in parts.items():
        if value == "":
            raise ValueError(f"{name} cannot be empty")
        if ":" in value:
            raise ValueError(f"{name} cannot contain ':'")
    return ":".join(parts.values())
