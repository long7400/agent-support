"""Tests for middleware stack ordering."""

from app.agent_harness.middleware import (
    build_default_middleware_stack,
    TenantContextMiddleware,
    PlatformContextMiddleware,
    MemoryMiddleware,
    DynamicPromptMiddleware,
    ContextBudgetMiddleware,
    ModelPolicyMiddleware,
    CapabilityRegistryMiddleware,
    ToolGuardMiddleware,
    RiskPolicyMiddleware,
    HumanApprovalMiddleware,
    ObservabilityMiddleware,
)


def test_middleware_stack_has_all_middleware():
    """Default stack should include all 11 middleware components."""
    stack = build_default_middleware_stack()

    assert len(stack) == 11

    # Verify each middleware type is present
    middleware_types = [type(m) for m in stack]

    assert TenantContextMiddleware in middleware_types
    assert PlatformContextMiddleware in middleware_types
    assert MemoryMiddleware in middleware_types
    assert DynamicPromptMiddleware in middleware_types
    assert ContextBudgetMiddleware in middleware_types
    assert ModelPolicyMiddleware in middleware_types
    assert CapabilityRegistryMiddleware in middleware_types
    assert ToolGuardMiddleware in middleware_types
    assert RiskPolicyMiddleware in middleware_types
    assert HumanApprovalMiddleware in middleware_types
    assert ObservabilityMiddleware in middleware_types


def test_middleware_stack_order():
    """Middleware must execute in the correct order per spec requirements.

    Order follows spec requirements:
    1. TenantContext - tenant status/profile first (before any processing)
    2. PlatformContext - platform constraints
    3. Memory - load memory before prompt building
    4. DynamicPrompt - build prompt using memory
    5. ContextBudget - compact if needed before model
    6. ModelPolicy - model selection and limits
    7. CapabilityRegistry - filter capabilities before tool guard
    8. ToolGuard - wrap tool calls with validation
    9. RiskPolicy - evaluate risk after model
    10. HumanApproval - HITL placeholder (Phase 6)
    11. Observability - wraps entire run
    """
    stack = build_default_middleware_stack()

    # Verify exact order
    assert isinstance(stack[0], TenantContextMiddleware)
    assert isinstance(stack[1], PlatformContextMiddleware)
    assert isinstance(stack[2], MemoryMiddleware)
    assert isinstance(stack[3], DynamicPromptMiddleware)
    assert isinstance(stack[4], ContextBudgetMiddleware)
    assert isinstance(stack[5], ModelPolicyMiddleware)
    assert isinstance(stack[6], CapabilityRegistryMiddleware)
    assert isinstance(stack[7], ToolGuardMiddleware)
    assert isinstance(stack[8], RiskPolicyMiddleware)
    assert isinstance(stack[9], HumanApprovalMiddleware)
    assert isinstance(stack[10], ObservabilityMiddleware)


def test_tenant_context_before_prompt():
    """TenantContext must execute before DynamicPrompt.

    Spec: 'tenant/platform before prompt'
    """
    stack = build_default_middleware_stack()

    tenant_idx = next(i for i, m in enumerate(stack) if isinstance(m, TenantContextMiddleware))
    prompt_idx = next(i for i, m in enumerate(stack) if isinstance(m, DynamicPromptMiddleware))

    assert tenant_idx < prompt_idx, "TenantContext must execute before DynamicPrompt"


def test_memory_before_prompt():
    """Memory must load before prompt building.

    Spec: 'memory/context before model'
    """
    stack = build_default_middleware_stack()

    memory_idx = next(i for i, m in enumerate(stack) if isinstance(m, MemoryMiddleware))
    prompt_idx = next(i for i, m in enumerate(stack) if isinstance(m, DynamicPromptMiddleware))

    assert memory_idx < prompt_idx, "Memory must load before DynamicPrompt"


def test_capability_registry_before_tool_guard():
    """CapabilityRegistry must filter before ToolGuard validates.

    Spec: 'capability registry before tool guard'
    """
    stack = build_default_middleware_stack()

    registry_idx = next(i for i, m in enumerate(stack) if isinstance(m, CapabilityRegistryMiddleware))
    guard_idx = next(i for i, m in enumerate(stack) if isinstance(m, ToolGuardMiddleware))

    assert registry_idx < guard_idx, "CapabilityRegistry must execute before ToolGuard"


def test_risk_policy_before_outbound():
    """RiskPolicy must evaluate before outbound delivery.

    Spec: 'risk/policy before outbound'
    """
    stack = build_default_middleware_stack()

    risk_idx = next(i for i, m in enumerate(stack) if isinstance(m, RiskPolicyMiddleware))
    approval_idx = next(i for i, m in enumerate(stack) if isinstance(m, HumanApprovalMiddleware))

    assert risk_idx < approval_idx, "RiskPolicy must evaluate before HumanApproval (outbound gate)"


def test_observability_wraps_everything():
    """Observability must be last to wrap the entire run.

    Spec: 'observability wraps the full run'
    """
    stack = build_default_middleware_stack()

    # Observability should be the last middleware
    assert isinstance(stack[-1], ObservabilityMiddleware)


def test_stack_accepts_custom_dependencies():
    """Stack should accept custom dependency injection for testing."""
    async def mock_profile_loader(tenant_id):
        return {}

    async def mock_prompt_builder(context):
        return "mock prompt"

    stack = build_default_middleware_stack(
        profile_loader=mock_profile_loader,
        prompt_builder=mock_prompt_builder,
    )

    assert len(stack) == 11
    assert isinstance(stack[0], TenantContextMiddleware)
    assert stack[0]._profile_loader is mock_profile_loader
    assert isinstance(stack[3], DynamicPromptMiddleware)
    assert stack[3]._prompt_builder is mock_prompt_builder
