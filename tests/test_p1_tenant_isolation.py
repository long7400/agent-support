"""P1 tenant isolation guardrail tests."""

import ast
from pathlib import Path

MIGRATION = Path("alembic/versions/7b3d2e8f9a10_p1_tenant_control_plane.py")
TENANT_ADMIN_API = Path("app/api/v1/tenant_admin.py")


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text()
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == function_name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"{function_name} not found in {path}")


def test_migration_enables_forced_rls_on_tenant_owned_tables() -> None:
    """Tenant-owned tables are protected by forced PostgreSQL RLS policies."""
    source = MIGRATION.read_text()

    for table in ("tenant_memberships", "service_principals", "tenant_config_versions", "audit_events"):
        assert f'"{table}"' in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "current_setting('app.current_tenant', true)" in source
    assert "USING (tenant_id" in source
    assert "WITH CHECK (tenant_id" in source


def test_tenant_context_uses_set_local_transaction_scope() -> None:
    """Tenant context helper uses SET LOCAL rather than connection-persistent SET."""
    source = Path("app/core/tenant_context.py").read_text()

    assert "async with session.begin()" in source
    assert "SET LOCAL app.current_tenant" in source
    assert "SET app.current_tenant" not in source


def test_update_tenant_route_uses_tenant_context() -> None:
    """Operator tenant updates run under the target tenant RLS context."""
    source = _function_source(TENANT_ADMIN_API, "update_tenant")

    assert "with_tenant_context(session, tenant_id)" in source
    assert "session.begin()" not in source


def test_add_member_route_uses_tenant_context() -> None:
    """Operator membership upserts run under the target tenant RLS context."""
    source = _function_source(TENANT_ADMIN_API, "add_member")

    assert "with_tenant_context(session, tenant_id)" in source
    assert "session.begin()" not in source


def test_tenant_admin_routes_map_service_errors() -> None:
    """Tenant admin routes translate service exceptions before FastAPI returns them."""
    source = TENANT_ADMIN_API.read_text()

    assert "def tenant_control_plane_http_error(exc: TenantControlPlaneError) -> HTTPException" in source
    assert "except TenantControlPlaneError as exc" in _function_source(TENANT_ADMIN_API, "update_tenant")
    assert "except TenantControlPlaneError as exc" in _function_source(TENANT_ADMIN_API, "add_member")
    assert "raise tenant_control_plane_http_error(exc) from exc" in source


def test_tenant_membership_dependencies_use_tenant_context() -> None:
    """Membership auth dependencies read RLS-protected memberships under tenant context."""
    source = Path("app/api/v1/auth.py").read_text()

    assert "from app.core.tenant_context import with_tenant_context" in source
    assert source.count("with_tenant_context(session, tenant_id)") >= 2


def test_service_principal_auth_is_tenant_scoped() -> None:
    """Service-principal auth requires trusted tenant id before RLS-protected lookup."""
    source = Path("app/services/tenant_control_plane.py").read_text()

    assert "api_key: str," in source
    assert "tenant_id: UUID," in source
    assert "ServicePrincipal.tenant_id == tenant_id" in source
