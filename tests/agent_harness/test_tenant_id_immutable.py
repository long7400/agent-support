"""Tests for tenant_id immutability in harness contracts."""

from uuid import UUID, uuid4

import pytest

from app.agent_harness.contracts import AgentRunState, apply_state_update
from app.agent_harness.errors import TenantIdImmutableError


def _make_state(tenant_id: UUID | None = None) -> AgentRunState:
    tid = tenant_id or uuid4()
    return AgentRunState(
        trace_id="test-trace",
        tenant_id=tid,
        input_event_id="evt-1",
        platform="telegram",
        channel_id="chan-1",
        thread_id=None,
        user_id_hash="hash-abc",
        message_id="msg-1",
        inbound_text_preview="hello",
        messages=[],
        tenant_context={},
        platform_context={},
        memory_context={},
        available_capabilities=[],
        tool_results=[],
        policy_decisions=[],
        risk_signals=[],
        budgets={},
        final_response=None,
        audit_refs=[],
    )


class TestTenantIdImmutable:
    """Tenant_id must be immutable after hydration."""

    def test_valid_update_allows_same_tenant_id(self) -> None:
        """Updating with the same tenant_id is allowed."""
        state = _make_state()
        tid = state["tenant_id"]
        result = apply_state_update(state, {"tenant_id": tid, "messages": [{"role": "user", "content": "hi"}]})
        assert result["tenant_id"] == tid
        assert result["messages"] == [{"role": "user", "content": "hi"}]

    def test_valid_update_without_tenant_id(self) -> None:
        """Updating without tenant_id is allowed."""
        state = _make_state()
        result = apply_state_update(state, {"messages": [{"role": "user", "content": "hi"}]})
        assert result["tenant_id"] == state["tenant_id"]

    def test_raises_on_tenant_id_change_after_hydration(self) -> None:
        """Changing tenant_id after hydration raises TenantIdImmutableError."""
        state = _make_state()
        other_tid = uuid4()
        with pytest.raises(TenantIdImmutableError) as exc:
            apply_state_update(state, {"tenant_id": other_tid})
        assert str(state["tenant_id"]) in str(exc.value)
        assert str(other_tid) in str(exc.value)

    def test_raises_on_tenant_id_change_with_multiple_updates(self) -> None:
        """Changing tenant_id in a batch update raises TenantIdImmutableError."""
        state = _make_state()
        other_tid = uuid4()
        with pytest.raises(TenantIdImmutableError):
            apply_state_update(state, {"tenant_id": other_tid, "messages": [{"role": "user", "content": "hi"}]})

    def test_initial_hydration_allows_tenant_id_set(self) -> None:
        """Setting tenant_id on initial hydration (state has None) is allowed."""
        state = AgentRunState(
            trace_id="test",
            tenant_id=None,  # type: ignore[typeddict-item]
            input_event_id="evt-1",
            platform="telegram",
            channel_id="chan-1",
            thread_id=None,
            user_id_hash="hash",
            message_id="msg-1",
            inbound_text_preview="hello",
            messages=[],
            tenant_context={},
            platform_context={},
            memory_context={},
            available_capabilities=[],
            tool_results=[],
            policy_decisions=[],
            risk_signals=[],
            budgets={},
            final_response=None,
            audit_refs=[],
        )
        tid = uuid4()
        result = apply_state_update(state, {"tenant_id": tid})
        assert result["tenant_id"] == tid
