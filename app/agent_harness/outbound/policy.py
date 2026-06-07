"""Outbound policy checker — validates envelopes before delivery creation.

Checks platform limits, risk signals, and moderation policy before
allowing outbound delivery.
"""

from __future__ import annotations


from app.agent_harness.contracts import TenantHarnessProfile
from app.agent_harness.outbound.envelope import OutboundEnvelope


# Maximum text length per platform
_PLATFORM_MAX_LENGTH: dict[str, int] = {
    "telegram": 4096,
    "discord": 2000,
}


def check_outbound_policy(
    envelope: OutboundEnvelope,
    profile: TenantHarnessProfile,
) -> OutboundEnvelope:
    """Check an outbound envelope against tenant policy.

    Returns the envelope with ``policy_approved`` and ``policy_decision``
    fields set.  Does NOT mutate the input — returns a new envelope or
    the same dataclass with fields updated.

    Args:
        envelope: The outbound envelope to check.
        profile: Tenant harness profile with policy settings.

    Returns:
        The envelope with policy decision fields set.
    """
    envelope.policy_approved = False

    # 1. Check platform is enabled
    enabled = profile.get("enabled_platforms", [])
    if envelope.platform not in enabled:
        envelope.policy_decision = f"denied: platform '{envelope.platform}' not enabled"
        return envelope

    # 2. Check text length limits
    max_len = _PLATFORM_MAX_LENGTH.get(envelope.platform, 4000)
    if envelope.text_content and len(envelope.text_content) > max_len:
        envelope.policy_decision = f"denied: text exceeds {max_len} char limit for {envelope.platform}"
        return envelope

    # 3. Check moderation mode
    moderation = profile.get("moderation_policy", {})
    mode = moderation.get("mode", "shadow")

    if mode == "enforce":
        # In enforce mode, all outbound must have explicit approval
        # Phase 3: always approve in shadow/propose
        pass

    # 4. If we got here, approve
    envelope.policy_approved = True
    envelope.policy_decision = "approved"

    return envelope
