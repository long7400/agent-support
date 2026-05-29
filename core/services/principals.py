from dataclasses import dataclass


@dataclass(frozen=True)
class AdminPrincipal:
    actor_type: str
    actor_id: str


@dataclass(frozen=True)
class AdapterPrincipal:
    actor_type: str
    actor_id: str
    platform: str
    external_workspace_id: str
    external_channel_id: str
