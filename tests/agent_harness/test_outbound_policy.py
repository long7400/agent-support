"""Tests for outbound policy — delivery only after policy check."""

from uuid import uuid4

from app.agent_harness.contracts import TenantHarnessProfile
from app.agent_harness.outbound.envelope import OutboundEnvelope
from app.agent_harness.outbound.policy import check_outbound_policy


def _make_profile(
    enabled_platforms: list[str] | None = None,
    moderation_mode: str = "shadow",
) -> TenantHarnessProfile:
    """Create a test tenant harness profile."""
    return TenantHarnessProfile(
        tenant_id=uuid4(),
        config_version=1,
        policy_version=1,
        enabled_platforms=enabled_platforms or ["telegram", "discord"],
        allowed_capabilities=["fake_search"],
        model_policy={},
        memory_policy={},
        moderation_policy={"mode": moderation_mode},
        escalation_policy={},
        budgets={},
    )


class TestOutboundPolicy:
    """Outbound must only occur after policy check passes."""

    def test_approves_allowed_platform(self) -> None:
        """A valid envelope for an enabled platform should be approved."""
        envelope = OutboundEnvelope(
            platform="telegram",
            channel_id=uuid4(),
            text_content="Hello, user!",
        )
        profile = _make_profile()
        result = check_outbound_policy(envelope, profile)
        assert result.policy_approved is True
        assert result.policy_decision == "approved"

    def test_denies_disabled_platform(self) -> None:
        """A disabled platform should be denied."""
        envelope = OutboundEnvelope(
            platform="discord",
            channel_id=uuid4(),
            text_content="Hello!",
        )
        profile = _make_profile(enabled_platforms=["telegram"])  # discord NOT enabled
        result = check_outbound_policy(envelope, profile)
        assert result.policy_approved is False
        assert "denied" in result.policy_decision
        assert "discord" in result.policy_decision

    def test_denies_oversized_text(self) -> None:
        """Overly long text should be denied."""
        envelope = OutboundEnvelope(
            platform="telegram",
            channel_id=uuid4(),
            text_content="x" * 5000,  # telegram max is 4096
        )
        profile = _make_profile()
        result = check_outbound_policy(envelope, profile)
        assert result.policy_approved is False
        assert "denied" in result.policy_decision

    def test_approves_within_length_limit(self) -> None:
        """Text within platform length limit should be approved."""
        envelope = OutboundEnvelope(
            platform="discord",
            channel_id=uuid4(),
            text_content="x" * 1500,  # discord max is 2000
        )
        profile = _make_profile()
        result = check_outbound_policy(envelope, profile)
        assert result.policy_approved is True

    def test_enforce_mode_still_approves_in_phase3(self) -> None:
        """Enforce mode still approves in Phase 3 (full enforcement in Phase 5)."""
        envelope = OutboundEnvelope(
            platform="telegram",
            channel_id=uuid4(),
            text_content="Hello!",
        )
        profile = _make_profile(moderation_mode="enforce")
        result = check_outbound_policy(envelope, profile)
        assert result.policy_approved is True
