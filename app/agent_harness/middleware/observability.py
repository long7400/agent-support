"""ObservabilityMiddleware — redacted trace events, latency, and replay refs."""

from __future__ import annotations

import time

from app.agent_harness.contracts import AgentRunState, HarnessContext


class ObservabilityMiddleware:
    """Emit redacted trace events and collect latency data for monitoring.

    Phase 3: logs structured events.  Full Langfuse/tracing integration
    arrives in Phase 4.
    """

    def __init__(self) -> None:
        """Initialize the middleware."""
        self._start_times: dict[str, float] = {}

    async def before_agent(self, state: AgentRunState, context: HarnessContext) -> None:
        """Record run start time."""
        trace_id = context.get("trace_id")
        if trace_id:
            self._start_times[trace_id] = time.time()

    async def after_agent(self, state: AgentRunState, context: HarnessContext) -> None:
        """Emit final trace metadata."""
        trace_id = context.get("trace_id")
        latency_ms = 0
        if trace_id and trace_id in self._start_times:
            latency_ms = int((time.time() - self._start_times[trace_id]) * 1000)
            del self._start_times[trace_id]
        state["_trace_metadata"] = {"latency_ms": latency_ms}
