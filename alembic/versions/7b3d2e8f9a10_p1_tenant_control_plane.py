"""P1 tenant control plane.

Revision ID: 7b3d2e8f9a10
Revises: b25d38b0cd7c
Create Date: 2026-06-06 11:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "7b3d2e8f9a10"
down_revision: Union[str, Sequence[str], None] = "b25d38b0cd7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_OWNED_TABLES = (
    "tenant_memberships",
    "service_principals",
    "tenant_config_versions",
    "audit_events",
)

def _create_rls_policy(table_name: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation ON {table_name}
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            """
        )
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("config_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("retention_policy_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active','disabled','suspended','deleting')", name="ck_tenants_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_table(
        "tenant_roles",
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )
    op.bulk_insert(
        sa.table("tenant_roles", sa.column("name", sa.String())),
        [{"name": "admin"}, {"name": "moderator"}, {"name": "viewer"}],
    )
    op.create_table(
        "tenant_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('admin','moderator','viewer')", name="ck_tenant_memberships_role"),
        sa.ForeignKeyConstraint(["role"], ["tenant_roles.name"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_memberships_tenant_user"),
    )
    op.create_index("idx_tenant_memberships_user", "tenant_memberships", ["user_id"], unique=False)
    op.create_table(
        "service_principals",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column("key_fingerprint", sa.String(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), server_default=sa.text("ARRAY[]::text[]"), nullable=False),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active','revoked','expired')", name="ck_service_principals_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_service_principals_tenant", "service_principals", ["tenant_id"], unique=False)
    op.create_index("idx_service_principals_key_prefix", "service_principals", ["key_prefix"], unique=False)
    op.create_table(
        "tenant_config_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("persona", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("official_links", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("moderation_mode", sa.String(), server_default="shadow", nullable=False),
        sa.Column("model_budget", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by_actor_type", sa.String(), server_default="operator", nullable=False),
        sa.Column("created_by_actor_id", sa.String(), server_default="system", nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("moderation_mode IN ('shadow','propose','enforce')", name="ck_tenant_config_versions_moderation_mode"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "version", name="uq_tenant_config_versions_tenant_version"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_type", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_events_tenant_action", "audit_events", ["tenant_id", "action"], unique=False)
    for table_name in TENANT_OWNED_TABLES:
        _create_rls_policy(table_name)


def downgrade() -> None:
    """Downgrade schema."""
    for table_name in reversed(TENANT_OWNED_TABLES):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}"))
        op.execute(sa.text(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"))
    op.drop_index("idx_audit_events_tenant_action", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("tenant_config_versions")
    op.drop_index("idx_service_principals_key_prefix", table_name="service_principals")
    op.drop_index("idx_service_principals_tenant", table_name="service_principals")
    op.drop_table("service_principals")
    op.drop_index("idx_tenant_memberships_user", table_name="tenant_memberships")
    op.drop_table("tenant_memberships")
    op.drop_table("tenant_roles")
    op.drop_table("tenants")
