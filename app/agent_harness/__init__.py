"""Agent Harness Runtime — deterministic, replayable agent execution.

Phase 3 replaces the echo stub in ProcessingOutboxWorker with a full harness
runtime: middleware stack, fake model/tool fixtures, policy-checked envelopes,
auditable run records, and deterministic replay.
"""

from app.agent_harness.version import HARNESS_VERSION

__all__ = ["HARNESS_VERSION"]
