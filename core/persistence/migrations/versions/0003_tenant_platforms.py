"""tenant platforms

Revision ID: 0003_tenant_platforms
Revises: 0002_tenant_control_plane
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_tenant_platforms"
down_revision: str | None = "0002_tenant_control_plane"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_platforms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("external_workspace_id", sa.String(length=255), nullable=False),
        sa.Column("external_channel_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "platform",
            "external_workspace_id",
            "external_channel_id",
            name="uq_tenant_platforms_platform_external_identity",
        ),
    )
    op.create_index("ix_tenant_platforms_tenant_id", "tenant_platforms", ["tenant_id"])
    op.create_index("ix_tenant_platforms_platform", "tenant_platforms", ["platform"])
    op.create_index(
        "ix_tenant_platforms_external_identity",
        "tenant_platforms",
        ["platform", "external_workspace_id", "external_channel_id"],
    )

    op.execute("ALTER TABLE tenant_platforms ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_platforms FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_tenant_platforms ON tenant_platforms
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_platforms TO agent_support_app")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON tenant_platforms FROM agent_support_app")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_tenant_platforms ON tenant_platforms")
    op.drop_index("ix_tenant_platforms_external_identity", table_name="tenant_platforms")
    op.drop_index("ix_tenant_platforms_platform", table_name="tenant_platforms")
    op.drop_index("ix_tenant_platforms_tenant_id", table_name="tenant_platforms")
    op.drop_table("tenant_platforms")
