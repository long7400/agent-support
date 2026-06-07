"""Tests for disabled tenant fail-closed behavior."""

import anyio
from unittest.mock import Mock
from app.agent_harness.errors import TenantDisabledError
from app.agent_harness.middleware.tenant_context import TenantContextMiddleware


def test_disabled_tenant_raises_error():
    """Disabled tenant must raise TenantDisabledError before model/tool/outbound.

    Spec: 'Disabled tenant stops before model/tool/outbound'
    """
    middleware = TenantContextMiddleware()

    # Create a context with a disabled tenant
    context = Mock()
    context.tenant_id = "tenant-disabled"
    context.profile = {
        "tenant_id": "tenant-disabled",
        "status": "disabled",
    }
    context.config = {
        "tenant_id": "tenant-disabled",
        "status": "disabled",
    }

    state = {
        "tenant_id": "tenant-disabled",
        "tenant_context": {"status": "disabled"},
    }

    # TenantContext should raise TenantDisabledError
    try:
        anyio.run(middleware.before_agent, state, context)
        raise AssertionError("Expected TenantDisabledError")
    except TenantDisabledError as e:
        assert "disabled" in str(e).lower()


def test_suspended_tenant_raises_error():
    """Suspended tenant must raise TenantDisabledError.

    Similar to disabled, suspended tenants cannot process requests.
    """
    middleware = TenantContextMiddleware()

    context = Mock()
    context.tenant_id = "tenant-suspended"
    context.profile = {
        "tenant_id": "tenant-suspended",
        "status": "suspended",
    }
    context.config = {
        "tenant_id": "tenant-suspended",
        "status": "suspended",
    }

    state = {
        "tenant_id": "tenant-suspended",
        "tenant_context": {"status": "suspended"},
    }

    try:
        anyio.run(middleware.before_agent, state, context)
        raise AssertionError("Expected TenantDisabledError")
    except TenantDisabledError as e:
        assert "suspended" in str(e).lower()


def test_active_tenant_passes_through():
    """Active tenant must pass through TenantContext without error."""

    # Create a custom profile loader that returns the expected profile
    async def mock_profile_loader(tenant_id):
        return {
            "tenant_id": tenant_id,
            "status": "active",
            "plan": "professional",
            "limits": {"max_requests_per_minute": 100},
            "config_version": 42,
            "policy_version": 7,
            "enabled_platforms": ["telegram", "discord"],
            "allowed_capabilities": ["rag.search"],
        }

    middleware = TenantContextMiddleware(profile_loader=mock_profile_loader)

    state = {
        "tenant_id": "tenant-active",
        "tenant_context": {"status": "active"},
    }

    # Should not raise
    result = anyio.run(middleware.before_agent, state, Mock())

    # State should be updated with tenant context
    assert "tenant_context" in result
    assert result["tenant_context"]["profile"]["plan"] == "professional"
    assert result["tenant_context"]["config_version"] == 42


def test_tenant_context_populates_state():
    """TenantContext must populate tenant_context in state."""
    middleware = TenantContextMiddleware()

    context = Mock()
    context.tenant_id = "tenant-test"
    context.profile = {
        "tenant_id": "tenant-test",
        "status": "active",
        "plan": "starter",
        "limits": {"max_requests_per_minute": 50},
        "features": {"rag_enabled": True, "custom_prompts": False},
    }
    context.config = {
        "tenant_id": "tenant-test",
        "status": "active",
    }

    state = {
        "tenant_id": "tenant-test",
        "tenant_context": {"status": "active"},
    }

    result = anyio.run(middleware.before_agent, state, context)

    # Verify tenant_context is populated
    assert "tenant_context" in result
    tenant_ctx = result["tenant_context"]

    assert tenant_ctx["status"] == "active"


def test_missing_tenant_id_raises_error():
    """Missing tenant_id must raise TenantDisabledError.

    Fail-closed: if we can't identify the tenant, deny the request.
    """
    middleware = TenantContextMiddleware()

    context = Mock()
    context.tenant_id = None

    state = {
        "tenant_context": {"status": "active"},
    }

    try:
        anyio.run(middleware.before_agent, state, context)
        raise AssertionError("Expected TenantDisabledError")
    except TenantDisabledError as e:
        assert "none" in str(e).lower()


def test_tenant_context_mutates_state():
    """TenantContext mutates the state dict in place.

    The middleware modifies the state dict directly for efficiency.
    This is acceptable because the state is created fresh for each run.
    """

    # Create a custom profile loader
    async def mock_profile_loader(tenant_id):
        return {
            "tenant_id": tenant_id,
            "status": "active",
            "config_version": 99,
            "policy_version": 11,
            "enabled_platforms": ["telegram"],
            "allowed_capabilities": ["rag.search"],
        }

    middleware = TenantContextMiddleware(profile_loader=mock_profile_loader)

    state = {
        "tenant_id": "tenant-test",
        "tenant_context": {},
    }

    result = anyio.run(middleware.before_agent, state, Mock())

    # Result should be the same dict (mutated in place)
    assert result is state
    # State should now have tenant_context populated
    assert "profile" in result["tenant_context"]
    assert result["tenant_context"]["config_version"] == 99
    assert "enabled_platforms" in result["tenant_context"]
