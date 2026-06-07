"""Tests for the harness runner — verifies runner creates run records and policy-checked envelopes.

Uses mocked DB session to avoid requiring a real database.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import anyio

from app.agent_harness.runner import HarnessRunner
from app.models.messaging import ChatEvent, ProcessingOutbox


def _make_session() -> AsyncMock:
    """Create a mock async session with properly configured execute."""
    session = AsyncMock()

    # Make session.execute().scalar_one_or_none() return None (no existing data)
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = None
    session.execute.return_value = scalar_result

    # Make flush and commit no-ops
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    return session


def _make_processing_row(**kwargs) -> MagicMock:
    """Create a minimal ProcessingOutbox mock."""
    row = MagicMock(spec=ProcessingOutbox)
    row.id = kwargs.get("id", uuid4())
    row.tenant_id = kwargs.get("tenant_id", uuid4())
    row.chat_event_id = kwargs.get("chat_event_id", uuid4())
    row.status = "processing"
    return row


def _make_chat_event(**kwargs) -> MagicMock:
    """Create a minimal ChatEvent mock."""
    event = MagicMock(spec=ChatEvent)
    event.id = kwargs.get("id", uuid4())
    event.tenant_id = kwargs.get("tenant_id", uuid4())
    event.platform = kwargs.get("platform", "telegram")
    event.channel_id = kwargs.get("channel_id", uuid4())
    event.thread_id = kwargs.get("thread_id", None)
    event.user_id = kwargs.get("user_id", "user-abc")
    event.message_type = "text"
    event.text_preview = kwargs.get("text_preview", "hello")
    event.metadata_json = {}
    return event


class TestHarnessRunner:
    """HarnessRunner creates run records and policy-checked envelopes."""

    def test_runner_initializes_with_defaults(self) -> None:
        """Runner should initialize with default model and registry."""
        runner = HarnessRunner()
        assert runner._model is not None
        assert runner._capability_registry is not None
        assert len(runner._middleware_stack) > 0

    def test_run_event_returns_result_and_envelope(self) -> None:
        """Runner should return a tuple of (HarnessResult, OutboundEnvelope)."""

        async def _run() -> None:
            session = _make_session()
            processing_row = _make_processing_row()
            chat_event = _make_chat_event(text_preview="hello")
            runner = HarnessRunner()
            result, envelope = await runner.run_event(session, processing_row, chat_event)
            assert result is not None
            assert result.get("status") == "completed"
            assert result.get("response_text") != ""
            assert envelope is not None

        anyio.run(_run)

    def test_run_event_returns_result_with_agent_run_id(self) -> None:
        """Runner should return a result with agent_run_id."""

        async def _run() -> None:
            session = _make_session()
            processing_row = _make_processing_row()
            chat_event = _make_chat_event(text_preview="hello")
            runner = HarnessRunner()
            result, envelope = await runner.run_event(session, processing_row, chat_event)
            assert result.get("agent_run_id") is not None

        anyio.run(_run)

    def test_runner_builds_envelope_with_idempotency_key(self) -> None:
        """Envelope should have a deterministic idempotency key."""

        async def _run() -> None:
            session = _make_session()
            processing_row = _make_processing_row()
            chat_event = _make_chat_event(text_preview="search for docs")
            runner = HarnessRunner()
            result, envelope = await runner.run_event(session, processing_row, chat_event)

            assert envelope is not None
            assert envelope.idempotency_key is not None
            assert envelope.idempotency_key.startswith("p3:harness:")

        anyio.run(_run)
