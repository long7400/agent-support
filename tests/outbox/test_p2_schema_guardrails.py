"""P2 schema guardrail tests - source-based validation."""

import re
from pathlib import Path


def test_migration_has_forced_rls() -> None:
    """Verify migration enables and forces RLS on all tenant-owned tables."""
    migration_path = Path(__file__).parent.parent.parent / "alembic/versions/a3f5c8e12d47_p2_platform_ingest.py"
    content = migration_path.read_text()

    tenant_owned_tables = [
        "tenant_platforms",
        "adapter_credentials",
        "platform_channels",
        "chat_events",
        "processing_outbox",
        "delivery_outbox",
        "delivery_receipts",
    ]

    # Verify all tables are in the TENANT_OWNED_TABLES tuple
    for table in tenant_owned_tables:
        assert f'"{table}"' in content, f"Table {table} not in TENANT_OWNED_TABLES"

    # Verify the helper function creates RLS policies
    assert "ENABLE ROW LEVEL SECURITY" in content
    assert "FORCE ROW LEVEL SECURITY" in content
    assert "CREATE POLICY tenant_isolation ON" in content

    # Verify helper is called for all tables via loop
    assert "for table_name in TENANT_OWNED_TABLES:" in content
    assert "_create_rls_policy(table_name)" in content


def test_migration_uses_current_setting_pattern() -> None:
    """Verify RLS policies use the current_setting pattern for tenant isolation."""
    migration_path = Path(__file__).parent.parent.parent / "alembic/versions/a3f5c8e12d47_p2_platform_ingest.py"
    content = migration_path.read_text()

    # Must use current_setting('app.current_tenant', true) pattern
    assert "current_setting('app.current_tenant', true)" in content
    assert "NULLIF(current_setting('app.current_tenant', true), '')::uuid" in content


def test_migration_has_required_unique_constraints() -> None:
    """Verify idempotency and uniqueness constraints exist."""
    migration_path = Path(__file__).parent.parent.parent / "alembic/versions/a3f5c8e12d47_p2_platform_ingest.py"
    content = migration_path.read_text()

    # Inbound idempotency
    assert "uq_chat_events_tenant_platform_message_direction" in content
    # Check for the constraint columns (formatting may vary)
    assert '"tenant_id"' in content and '"platform"' in content
    assert '"external_message_id"' in content and '"direction"' in content

    # Outbound idempotency
    assert "uq_delivery_outbox_tenant_idempotency" in content
    assert 'UniqueConstraint("tenant_id", "idempotency_key"' in content

    # Platform uniqueness
    assert "uq_tenant_platforms_tenant_platform_workspace" in content
    assert "uq_platform_channels_platform_channel_thread" in content


def test_migration_has_partial_indexes_for_pending() -> None:
    """Verify partial indexes exist for pending outbox rows."""
    migration_path = Path(__file__).parent.parent.parent / "alembic/versions/a3f5c8e12d47_p2_platform_ingest.py"
    content = migration_path.read_text()

    # Processing outbox pending index
    assert "idx_processing_outbox_pending" in content
    assert "postgresql_where=sa.text(\"status = 'pending' AND dead_letter = false\")" in content

    # Delivery outbox pending index
    assert "idx_delivery_outbox_pending" in content


def test_migration_has_outbox_worker_fields() -> None:
    """Verify outbox tables have worker claim/retry fields."""
    migration_path = Path(__file__).parent.parent.parent / "alembic/versions/a3f5c8e12d47_p2_platform_ingest.py"
    content = migration_path.read_text()

    required_fields = [
        "run_after_ts",
        "worker_id",
        "heartbeat_at",
        "retries",
        "last_error",
        "dead_letter",
    ]

    for field in required_fields:
        # Check both outbox tables have these fields
        pattern = rf'sa\.Column\("{field}"'
        matches = re.findall(pattern, content)
        assert len(matches) >= 2, f"Field {field} missing from outbox tables (found {len(matches)}, expected >= 2)"


def test_migration_has_check_constraints() -> None:
    """Verify check constraints for status/platform/direction/action fields."""
    migration_path = Path(__file__).parent.parent.parent / "alembic/versions/a3f5c8e12d47_p2_platform_ingest.py"
    content = migration_path.read_text()

    # Platform constraints
    assert "ck_tenant_platforms_platform" in content
    assert "platform IN ('telegram','discord')" in content

    # Status constraints
    assert "ck_tenant_platforms_status" in content
    assert "ck_adapter_credentials_status" in content
    assert "ck_platform_channels_status" in content
    assert "ck_processing_outbox_status" in content
    assert "ck_delivery_outbox_status" in content

    # Direction constraints
    assert "ck_chat_events_direction" in content
    assert "direction IN ('inbound','outbound')" in content

    # Message type constraints
    assert "ck_chat_events_message_type" in content
    assert "message_type IN ('text','command','media','system','edited')" in content

    # Action constraints
    assert "ck_delivery_outbox_action" in content
    assert "action IN ('send_message','edit_message','delete_message')" in content


def test_migration_has_skip_locked_prerequisites() -> None:
    """Verify migration structure supports FOR UPDATE SKIP LOCKED claims."""
    migration_path = Path(__file__).parent.parent.parent / "alembic/versions/a3f5c8e12d47_p2_platform_ingest.py"
    content = migration_path.read_text()

    # Outbox tables must have status and run_after_ts for claim queries
    assert "processing_outbox" in content
    assert "delivery_outbox" in content
    assert "run_after_ts" in content
    assert "status" in content

    # Partial indexes on pending rows optimize claim queries
    assert "idx_processing_outbox_pending" in content
    assert "idx_delivery_outbox_pending" in content


def test_migration_downgrade_reverses_rls() -> None:
    """Verify downgrade removes RLS policies and disables RLS."""
    migration_path = Path(__file__).parent.parent.parent / "alembic/versions/a3f5c8e12d47_p2_platform_ingest.py"
    content = migration_path.read_text()

    # Find downgrade function
    downgrade_match = re.search(r"def downgrade\(\).*?(?=\n\n|\Z)", content, re.DOTALL)
    assert downgrade_match, "Missing downgrade function"

    downgrade_code = downgrade_match.group(0)

    tenant_owned_tables = [
        "tenant_platforms",
        "adapter_credentials",
        "platform_channels",
        "chat_events",
        "processing_outbox",
        "delivery_outbox",
        "delivery_receipts",
    ]

    # Verify all tables are dropped
    for table in tenant_owned_tables:
        assert f'op.drop_table("{table}")' in downgrade_code, f"Missing drop_table for {table}"

    # Verify RLS cleanup via loop
    assert "for table_name in reversed(TENANT_OWNED_TABLES):" in downgrade_code
    assert "DROP POLICY IF EXISTS tenant_isolation ON" in downgrade_code
    assert "DISABLE ROW LEVEL SECURITY" in downgrade_code
