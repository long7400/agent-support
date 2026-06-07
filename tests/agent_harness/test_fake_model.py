"""Tests for deterministic fake model behavior."""

import anyio

from app.agent_harness.contracts import AgentRunState, HarnessContext
from app.agent_harness.models.fake_model import FakeModel


def test_fake_model_matches_fixture_and_records_call() -> None:
    """Fixture triggers should return configured responses and record metadata."""

    async def _run() -> None:
        state = AgentRunState(messages=[{"role": "user", "content": "hello there"}])
        model = FakeModel()

        response = await model.generate(state, HarnessContext())

        assert response == "Hello! How can I help you today?"
        assert model.call_count == 1
        assert state["model_calls_made"] == [
            {"provider": "fake", "model": "fake-model", "trigger": "hello", "call_number": 1}
        ]

    anyio.run(_run)


def test_fake_model_uses_default_for_unmatched_text() -> None:
    """Unmatched text should use the default deterministic response."""

    async def _run() -> None:
        state = AgentRunState(messages=[{"role": "user", "content": "unknown input"}])
        model = FakeModel(default_response="fallback")

        response = await model.generate(state, HarnessContext())

        assert response == "fallback"
        assert state["model_calls_made"][0]["trigger"] == "default"

    anyio.run(_run)


def test_fake_model_reset_clears_call_count() -> None:
    """Reset should clear the in-memory call counter."""
    model = FakeModel()
    model.call_count = 3

    model.reset()

    assert model.call_count == 0
