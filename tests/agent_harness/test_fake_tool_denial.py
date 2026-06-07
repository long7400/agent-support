"""Tests for fake tool denial — denied tools must be audited and never called."""

from uuid import uuid4

import anyio
import pytest

from app.agent_harness.contracts import AgentRunState, HarnessContext
from app.agent_harness.capabilities.registry import FakeCapabilityRegistry
from app.agent_harness.capabilities.fake_tools import fake_disabled_tool
from app.agent_harness.middleware.tool_guard import ToolGuardMiddleware
from app.agent_harness.errors import CapabilityDeniedError


def _make_state() -> AgentRunState:
    """Create a test state."""
    return AgentRunState(
        trace_id="test-trace",
        tenant_id=uuid4(),
        input_event_id="evt-1",
        platform="telegram",
        channel_id="chan-1",
        thread_id=None,
        user_id_hash="hash-abc",
        message_id="msg-1",
        inbound_text_preview="search for docs",
        messages=[{"role": "user", "content": "search for docs"}],
        tenant_context={"allowed_capabilities": ["fake_search", "official_links"]},
        platform_context={},
        memory_context={},
        available_capabilities=["fake_search", "official_links"],
        tool_results=[],
        policy_decisions=[],
        risk_signals=[],
        budgets={},
        final_response=None,
        audit_refs=[],
    )


class TestFakeToolDenial:
    """Verifies that denied tools are audited and never called."""

    def test_allowed_tool_proceeds(self) -> None:
        """An allowed tool should execute without error."""

        async def _run() -> None:
            state = _make_state()
            context: HarnessContext = HarnessContext(
                trace_id="test", tenant_id=uuid4(), deadline_ms=10000,
                run_mode="shadow", services={}, redaction_policy={},
            )
            registry = FakeCapabilityRegistry()
            result = await registry.execute(state, context, "fake_search", {"query": "docs"})
            assert "error" not in result
            assert result["source"] == "fake_rag"

        anyio.run(_run)

    def test_denied_tool_raises_via_tool_guard(self) -> None:
        """A denied tool should raise CapabilityDeniedError and not call the tool."""

        async def _run() -> None:
            state = _make_state()
            state["available_capabilities"] = ["fake_search"]  # disallowed_tool NOT in allowed
            context: HarnessContext = HarnessContext(
                trace_id="test", tenant_id=uuid4(), deadline_ms=10000,
                run_mode="shadow", services={}, redaction_policy={},
            )
            guard = ToolGuardMiddleware()

            # The callable that would have been the tool
            async def _tool_body() -> dict:
                return await fake_disabled_tool("disallowed_tool")

            with pytest.raises(CapabilityDeniedError) as exc:
                await guard.wrap_tool_call(state, context, "disallowed_tool", {}, _tool_body)

            assert "disallowed_tool" in str(exc.value)
            # Verify a policy decision was recorded
            assert len(state.get("policy_decisions", [])) > 0

        anyio.run(_run)

    def test_disallowed_tool_body_never_called(self) -> None:
        """The tool body for a disallowed tool should never execute."""

        async def _run() -> None:
            state = _make_state()
            state["available_capabilities"] = ["fake_search"]
            context: HarnessContext = HarnessContext(
                trace_id="test", tenant_id=uuid4(), deadline_ms=10000,
                run_mode="shadow", services={}, redaction_policy={},
            )
            guard = ToolGuardMiddleware()

            # If this gets called, it returns executed=True
            tool_executed = False

            async def _tool_body() -> dict:
                nonlocal tool_executed
                tool_executed = True
                return {"executed": True}

            with pytest.raises(CapabilityDeniedError):
                await guard.wrap_tool_call(state, context, "disallowed_tool", {}, _tool_body)

            assert not tool_executed, "Tool body was executed despite policy denial"

        anyio.run(_run)
