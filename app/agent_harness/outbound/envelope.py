"""OutboundEnvelope — policy-checked delivery intent.

Represents one outbound message that has passed (or will be checked by)
outbound policy.  The envelope is the unit of handoff from the harness
runtime to the delivery outbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class OutboundEnvelope:
    """A policy-checked delivery intent.

    Created by the harness runtime after the model/tool loop completes,
    then passed through ``check_outbound_policy()`` before delivery outbox
    creation.
    """

    platform: str
    channel_id: UUID
    thread_id: UUID | None = None
    action: str = "send_message"
    text_content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    agent_run_id: UUID | None = None
    idempotency_key: str | None = None
    policy_approved: bool = False
    policy_decision: str | None = None  # "approved", "denied", "shadow_approved"
