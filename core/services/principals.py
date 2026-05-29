from dataclasses import dataclass


@dataclass(frozen=True)
class AdminPrincipal:
    actor_type: str
    actor_id: str
