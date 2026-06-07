"""HarnessRunner — loads profile, creates run records, delegates to runtime.

Bridges the outbox worker (ProcessingOutbox + ChatEvent) to the harness
runtime, persists run records, and returns policy-checked outbound envelopes.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_harness.contracts import (
    HarnessResult,
    TenantHarnessProfile,
    TrustedRuntimeEvent,
)
from app.agent_harness.models.fake_model import FakeModel
from app.agent_harness.capabilities.registry import FakeCapabilityRegistry
from app.agent_harness.middleware.stack import build_default_middleware_stack
from app.agent_harness.outbound.envelope import OutboundEnvelope
from app.agent_harness.outbound.policy import check_outbound_policy
from app.agent_harness.persistence.repositories import (
    create_agent_run,
    complete_agent_run,
)
from app.agent_harness.runtime import AgentHarnessRuntime
from app.agent_harness.version import HARNESS_VERSION
from app.models.messaging import ChatEvent, ProcessingOutbox


class HarnessRunner:
    """Loads tenant profile, creates run records, and delegates to runtime.

    Phase 3: uses fake model, fake capability registry, and builds a flat
    tenant profile from the ``ProcessingOutbox`` row's tenant context.
    """

    def __init__(
        self,
        model: FakeModel | None = None,
        capability_registry: FakeCapabilityRegistry | None = None,
    ) -> None:
        """Initialize the runner.

        Args:
            model: Optional FakeModel instance (creates default if None).
            capability_registry: Optional FakeCapabilityRegistry (creates default if None).
        """
        self._model = model or FakeModel()
        self._capability_registry = capability_registry or FakeCapabilityRegistry()
        self._middleware_stack = build_default_middleware_stack()
        self._runtime = AgentHarnessRuntime(
            model=self._model,
            capability_registry=self._capability_registry,
            middleware_stack=self._middleware_stack,
        )

    async def run_event(
        self,
        session: AsyncSession,
        processing_row: ProcessingOutbox,
        chat_event: ChatEvent,
    ) -> tuple[HarnessResult, OutboundEnvelope | None]:
        """Process one processing_outbox row through the harness.

        Args:
            session: Database session inside tenant context.
            processing_row: The claimed processing_outbox row.
            chat_event: The associated ChatEvent (verified non-None by caller).

        Returns:
            Tuple of (HarnessResult, OutboundEnvelope or None).
        """
        # 1. Build trusted runtime event
        event = self._build_event(processing_row, chat_event)

        # 2. Build tenant profile
        profile = self._build_profile(processing_row.tenant_id, chat_event)

        # 3. Create agent run record
        run = await create_agent_run(
            session,
            tenant_id=processing_row.tenant_id,
            processing_outbox_id=processing_row.id,
            trace_id=str(event.get("event_id", "")),
            input_event_id=str(event.get("chat_event_id", "")),
            harness_version=HARNESS_VERSION,
            middleware_sequence=[type(mw).__name__ for mw in self._middleware_stack],
            config_version=profile.get("config_version", 1),
            policy_version=profile.get("policy_version", 1),
        )
        agent_run_id = run.id

        try:
            # 4. Run harness
            result = await self._runtime.run(event, profile, agent_run_id=agent_run_id)

            # 5. Complete agent run record
            await complete_agent_run(
                session,
                agent_run_id=agent_run_id,
                status=result.get("status", "completed"),
                final_response_preview=result.get("response_text", ""),
                latency_ms=result.get("latency_ms", 0),
            )

            # 6. Build outbound envelope (policy-checked)
            envelope = self._build_envelope(result, chat_event, agent_run_id, profile)
            if envelope:
                envelope = check_outbound_policy(envelope, profile)

            return result, envelope

        except Exception:
            # Mark run as failed
            await complete_agent_run(
                session,
                agent_run_id=agent_run_id,
                status="failed",
                final_response_preview=None,
                latency_ms=None,
            )
            raise

    def _build_event(
        self,
        processing_row: ProcessingOutbox,
        chat_event: ChatEvent,
    ) -> TrustedRuntimeEvent:
        """Build a TrustedRuntimeEvent from processing and chat data."""
        return {
            "event_id": processing_row.id,
            "tenant_id": processing_row.tenant_id,
            "chat_event_id": chat_event.id,
            "platform": chat_event.platform,  # type: ignore[typeddict-item]
            "channel_id": chat_event.channel_id,
            "thread_id": chat_event.thread_id,
            "user_id_hash": chat_event.user_id or "",
            "message_type": chat_event.message_type,
            "text_preview": chat_event.text_preview or "",
            "metadata": chat_event.metadata_json or {},
        }

    def _build_profile(
        self,
        tenant_id: UUID,
        chat_event: ChatEvent,
    ) -> TenantHarnessProfile:
        """Build a tenant harness profile from available data.

        Phase 3: flat defaults.  Full profile loading arrives in Phase 4.
        """
        return {
            "tenant_id": tenant_id,
            "config_version": 1,
            "policy_version": 1,
            "enabled_platforms": ["telegram", "discord"],
            "allowed_capabilities": ["fake_search", "official_links"],
            "model_policy": {"provider": "fake", "model": "fake-model"},
            "memory_policy": {"enabled": False},
            "moderation_policy": {"mode": "shadow"},
            "escalation_policy": {"enabled": False},
            "budgets": {"max_tokens": 4000, "max_model_calls": 5},
        }

    def _build_envelope(
        self,
        result: HarnessResult,
        chat_event: ChatEvent,
        agent_run_id: UUID,
        profile: TenantHarnessProfile,
    ) -> OutboundEnvelope | None:
        """Build an outbound envelope from the harness result."""
        response_text = result.get("response_text", "")
        if not response_text:
            return None

        return OutboundEnvelope(
            platform=chat_event.platform,
            channel_id=chat_event.channel_id,
            thread_id=chat_event.thread_id,
            action="send_message",
            text_content=response_text,
            metadata={
                "source": "harness",
                "harness_version": HARNESS_VERSION,
                "agent_run_id": str(agent_run_id),
                "status": result.get("status", "completed"),
            },
            agent_run_id=agent_run_id,
            idempotency_key=f"p3:harness:{chat_event.id}:{HARNESS_VERSION}",
            policy_approved=False,
        )
