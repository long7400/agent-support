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

from typing import Any, cast

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
    return cast(list[Middleware], [
        TenantContextMiddleware(profile_loader=kwargs.get("profile_loader")),
        PlatformContextMiddleware(),
        MemoryMiddleware(memory_loader=kwargs.get("memory_loader")),
        DynamicPromptMiddleware(prompt_builder=kwargs.get("prompt_builder")),
        ContextBudgetMiddleware(max_tokens=kwargs.get("max_tokens")),
        ModelPolicyMiddleware(model_selector=kwargs.get("model_selector")),
        CapabilityRegistryMiddleware(capability_filter=kwargs.get("capability_filter")),
        ToolGuardMiddleware(validator=kwargs.get("tool_validator")),
        RiskPolicyMiddleware(risk_detector=kwargs.get("risk_detector")),
        HumanApprovalMiddleware(approval_checker=kwargs.get("approval_checker")),
        ObservabilityMiddleware(),
    ])
