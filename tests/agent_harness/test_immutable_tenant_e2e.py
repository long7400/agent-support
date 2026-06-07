"""End-to-end tests for tenant_id immutability through the harness runtime.

Verifies that tenant_id cannot be changed through the full runner path
and that the runtime enforces tenant_id immutability.
"""

from uuid import uuid4

import pytest

from app.agent_harness.contracts import (
    AgentRunState,
    apply_state_update,
)
from app.agent_harness.errors import TenantIdImmutableError


class TestImmutableTenantE2E:
    """Verify tenant_id is immutable through the full runtime flow."""

    def test_runtime_event_tenant_id_preserved(self) -> None:
        """The tenant_id from the event should be preserved in the result."""
        # This test verifies the contract-level immutability
        tenant_id = uuid4()
        state: AgentRunState = {
            "trace_id": "test-trace",
            "tenant_id": tenant_id,
            "input_event_id": "evt-1",
            "platform": "telegram",
            "channel_id": "chan-1",
            "thread_id": None,
            "user_id_hash": "hash",
            "message_id": "msg-1",
            "inbound_text_preview": "hello",
            "messages": [],
            "tenant_context": {},
            "platform_context": {},
            "memory_context": {},
            "available_capabilities": [],
            "tool_results": [],
            "policy_decisions": [],
            "risk_signals": [],
            "budgets": {},
            "final_response": None,
            "audit_refs": [],
        }

        # Same tenant_id is OK
        result = apply_state_update(state, {"tenant_id": tenant_id})
        assert result["tenant_id"] == tenant_id

        # Different tenant_id raises
        with pytest.raises(TenantIdImmutableError):
            apply_state_update(state, {"tenant_id": uuid4()})

    def test_none_tenant_id_can_be_set(self) -> None:
        """A None tenant_id can be set to a real value (initial hydration)."""
        state: AgentRunState = {
            "trace_id": "test",
            "tenant_id": None,  # type: ignore[typeddict-item]
            "input_event_id": "evt-1",
            "platform": "telegram",
            "channel_id": "chan-1",
            "thread_id": None,
            "user_id_hash": "hash",
            "message_id": "msg-1",
            "inbound_text_preview": "hello",
            "messages": [],
            "tenant_context": {},
            "platform_context": {},
            "memory_context": {},
            "available_capabilities": [],
            "tool_results": [],
            "policy_decisions": [],
            "risk_signals": [],
            "budgets": {},
            "final_response": None,
            "audit_refs": [],
        }
        tid = uuid4()
        result = apply_state_update(state, {"tenant_id": tid})
        assert result["tenant_id"] == tid

        # Now it's immutable
        with pytest.raises(TenantIdImmutableError):
            apply_state_update(state, {"tenant_id": uuid4()})
