"""End-to-end tests for run/step/model record creation during a harness run.

Uses the harness runtime directly with fake fixtures.
No real DB — verifies that the runtime flow would create records.
"""

from uuid import uuid4

import anyio

from app.agent_harness.contracts import TrustedRuntimeEvent, TenantHarnessProfile
from app.agent_harness.models.fake_model import FakeModel
from app.agent_harness.capabilities.registry import FakeCapabilityRegistry
from app.agent_harness.middleware.stack import build_default_middleware_stack
from app.agent_harness.runtime import AgentHarnessRuntime


def _make_event() -> TrustedRuntimeEvent:
    tenant_id = uuid4()
    return {
        "event_id": uuid4(),
        "tenant_id": tenant_id,
        "chat_event_id": uuid4(),
        "platform": "telegram",
        "channel_id": uuid4(),
        "thread_id": None,
        "user_id_hash": "test-user-hash",
        "message_type": "text",
        "text_preview": "hello",
        "metadata": {},
    }


def _make_profile(event: TrustedRuntimeEvent) -> TenantHarnessProfile:
    return {
        "tenant_id": event["tenant_id"],
        "config_version": 1,
        "policy_version": 1,
        "enabled_platforms": ["telegram", "discord"],
        "allowed_capabilities": ["fake_search", "official_links"],
        "model_policy": {},
        "memory_policy": {},
        "moderation_policy": {"mode": "shadow"},
        "escalation_policy": {},
        "budgets": {},
    }


class TestRunRecordsE2E:
    """Verify that a harness run produces expected artifacts."""

    def test_run_produces_model_calls(self) -> None:
        """A harness run should produce model call entries in the result."""

        async def _run() -> None:
            event = _make_event()
            profile = _make_profile(event)
            model = FakeModel()
            registry = FakeCapabilityRegistry()
            middleware = build_default_middleware_stack()
            runtime = AgentHarnessRuntime(model, registry, middleware)
            result = await runtime.run(event, profile)
            assert len(result.get("model_calls_made", [])) > 0
            assert result.get("response_text", "") != ""

        anyio.run(_run)

    def test_run_status_is_completed(self) -> None:
        """A successful harness run should have status 'completed'."""

        async def _run() -> None:
            event = _make_event()
            profile = _make_profile(event)
            model = FakeModel()
            registry = FakeCapabilityRegistry()
            middleware = build_default_middleware_stack()
            runtime = AgentHarnessRuntime(model, registry, middleware)
            result = await runtime.run(event, profile)
            assert result.get("status") == "completed"

        anyio.run(_run)

    def test_run_has_agent_run_id(self) -> None:
        """A harness run should produce a unique agent_run_id."""

        async def _run() -> None:
            event = _make_event()
            profile = _make_profile(event)
            model = FakeModel()
            registry = FakeCapabilityRegistry()
            middleware = build_default_middleware_stack()
            runtime = AgentHarnessRuntime(model, registry, middleware)
            result = await runtime.run(event, profile)
            assert result.get("agent_run_id") is not None

        anyio.run(_run)

    def test_run_has_policy_decisions(self) -> None:
        """A harness run should produce policy decisions."""

        async def _run() -> None:
            event = _make_event()
            profile = _make_profile(event)
            model = FakeModel()
            registry = FakeCapabilityRegistry()
            middleware = build_default_middleware_stack()
            runtime = AgentHarnessRuntime(model, registry, middleware)
            result = await runtime.run(event, profile)
            # Policy decisions may be empty, but the key should exist
            assert "policy_decisions" in result

        anyio.run(_run)
