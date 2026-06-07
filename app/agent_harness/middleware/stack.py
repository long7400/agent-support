"""Default middleware stack builder — produces an ordered list of middleware.

Ordering reflects the harness lifecycle:

  1. before_agent:  tenant_context, platform_context, memory, observability
  2. before_model:  dynamic_prompt, context_budget, model_policy, capability_registry
  3. wrap_model_call:  model_policy (counter), observability
  4. after_model:   risk_policy
  5. wrap_tool_call:  tool_guard, human_approval
  6. after_agent:   risk_policy, memory, observability, tenant_context (no-op)
"""

from __future__ import annotations

from typing import Any

from app.agent_harness.middleware.base import Middleware
from app.agent_harness.middleware.capability_registry import CapabilityRegistryMiddleware
from app.agent_harness.middleware.context_budget import ContextBudgetMiddleware
from app.agent_harness.middleware.dynamic_prompt import DynamicPromptMiddleware
from app.agent_harness.middleware.human_approval import HumanApprovalMiddleware
from app.agent_harness.middleware.memory import MemoryMiddleware
from app.agent_harness.middleware.model_policy import ModelPolicyMiddleware
from app.agent_harness.middleware.observability import ObservabilityMiddleware
from app.agent_harness.middleware.platform_context import PlatformContextMiddleware
from app.agent_harness.middleware.risk_policy import RiskPolicyMiddleware
from app.agent_harness.middleware.tenant_context import TenantContextMiddleware
from app.agent_harness.middleware.tool_guard import ToolGuardMiddleware


async def execute_middleware_chain(
    middleware_stack: list[Middleware],
    hook: str,
    state: Any,
    context: Any,
    **kwargs: Any,
) -> Any:
    """Execute a hook across all middleware in order.

    Args:
        middleware_stack: Ordered list of middleware.
        hook: Hook name (before_agent, after_agent, before_model, after_model).
        state: Current agent run state.
        context: Harness context.
        **kwargs: Additional arguments for specific hooks.

    Returns:
        Updated state after all middleware have executed.
    """
    for middleware in middleware_stack:
        hook_method = getattr(middleware, hook, None)
        if hook_method:
            state = await hook_method(state, context, **kwargs)
    return state


async def execute_wrap_middleware_chain(
    middleware_stack: list[Middleware],
    hook: str,
    state: Any,
    context: Any,
    call: Any,
    **kwargs: Any,
) -> Any:
    """Execute a wrap hook across all middleware in order.

    Wrap hooks (wrap_model_call, wrap_tool_call) nest the actual call
    through each middleware layer.
    """
    wrapped_call = call
    for middleware in reversed(middleware_stack):
        hook_method = getattr(middleware, hook, None)
        if hook_method:

            async def _wrap(mw, nc):
                return await mw(state, context, nc, **kwargs)  # type: ignore[call-arg]

            def wrapped_call(mw=middleware, nc=wrapped_call):
                return _wrap(mw, nc)

    return await wrapped_call()


def build_default_middleware_stack(**kwargs: Any) -> list[Middleware]:
    """Build the default ordered middleware stack.

    The order is designed so that:
    - Tenant/platform checks happen first (fail fast)
    - Context/memory/prompt assembly happens before model
    - Capability filtering and tool guard happen before tool calls
    - Risk policy runs after model/tool output
    - Human approval wraps destructive actions
    - Observability wraps the full lifecycle
    """
    return [
        TenantContextMiddleware(),
        PlatformContextMiddleware(),
        MemoryMiddleware(),
        DynamicPromptMiddleware(),
        ContextBudgetMiddleware(),
        ModelPolicyMiddleware(),
        CapabilityRegistryMiddleware(),
        ToolGuardMiddleware(),
        RiskPolicyMiddleware(),
        HumanApprovalMiddleware(),
        ObservabilityMiddleware(),
    ]
