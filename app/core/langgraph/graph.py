"""LangGraph agent stub.

Phase 3: replaced by app/agent_harness/runtime.py.
This stub preserves the import path for backward compatibility
but delegates internally to the new harness runtime.

NOTE: This module is scheduled for removal in Phase 4.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.agent_harness.contracts import TrustedRuntimeEvent, TenantHarnessProfile
from app.agent_harness.models.fake_model import FakeModel
from app.agent_harness.capabilities.registry import FakeCapabilityRegistry
from app.agent_harness.middleware.stack import build_default_middleware_stack
from app.agent_harness.runtime import AgentHarnessRuntime


class LangGraphAgent:
    """Backward-compatible stub that delegates to the harness runtime.

    Preserves the public interface for any remaining callers.
    No real LLM calls — uses FakeModel.
    """

    def __init__(self) -> None:
        """Initialize with harness runtime components."""
        self._model = FakeModel()
        self._registry = FakeCapabilityRegistry()
        self._middleware = build_default_middleware_stack()
        self._runtime = AgentHarnessRuntime(self._model, self._registry, self._middleware)
        self._connection_pool = None

    async def get_response(
        self,
        messages: list[Any],
        session_id: str,
        user_id: str | None = None,
        username: str | None = None,
    ) -> list[Any]:
        """Get a response using the harness runtime.

        Returns a deterministic fake response with no real LLM call.
        """
        last_user_msg = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and hasattr(msg, "role") and msg.role == "user":
                last_user_msg = msg.content
                break
            elif isinstance(msg, dict) and msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break

        synthetic_tenant_id = uuid5(NAMESPACE_URL, session_id)
        event = cast(
            TrustedRuntimeEvent,
            {
                "event_id": uuid4(),
                "tenant_id": synthetic_tenant_id,
                "chat_event_id": uuid4(),
                "platform": "telegram",
                "channel_id": synthetic_tenant_id,
                "thread_id": None,
                "user_id_hash": user_id or "",
                "message_type": "text",
                "text_preview": last_user_msg,
                "metadata": {},
            },
        )

        profile = cast(
            TenantHarnessProfile,
            {
                "tenant_id": synthetic_tenant_id,
                "config_version": 1,
                "policy_version": 1,
                "enabled_platforms": ["telegram", "discord"],
                "allowed_capabilities": [],
                "model_policy": {},
                "memory_policy": {},
                "moderation_policy": {},
                "escalation_policy": {},
                "budgets": {},
            },
        )

        result = await self._runtime.run(event, profile)
        from app.schemas.chat import Message

        return [Message(role="assistant", content=result.get("response_text", "Fake response."))]

    async def create_graph(self) -> None:
        """Stub: no-op in Phase 3 (harness doesn't use LangGraph graphs)."""

    async def get_chat_history(self, session_id: str) -> list[Any]:
        """Stub: returns empty history."""
        return []

    async def clear_chat_history(self, session_id: str) -> None:
        """Stub: no-op."""
