"""foundation rls

Revision ID: 0001_foundation_rls
Revises:
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_foundation_rls"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_support_app') THEN
                CREATE ROLE agent_support_app LOGIN
                PASSWORD 'agent_support_app'; -- pragma: allowlist secret
            END IF;
        END
        $$;
        """
    )

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    op.create_table(
        "chat_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("channel_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_chat_events_tenant_id", "chat_events", ["tenant_id"])
    op.create_index("ix_chat_events_trace_id", "chat_events", ["trace_id"])

    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_tenants ON tenants
        USING (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """
    )
    op.execute("ALTER TABLE chat_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_chat_events ON chat_events
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO agent_support_app")
    op.execute("GRANT SELECT ON tenants TO agent_support_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON chat_events TO agent_support_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_chat_events ON chat_events")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_tenants ON tenants")
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON chat_events FROM agent_support_app")
    op.execute("REVOKE SELECT ON tenants FROM agent_support_app")
    op.execute("REVOKE USAGE ON SCHEMA public FROM agent_support_app")
    op.drop_index("ix_chat_events_trace_id", table_name="chat_events")
    op.drop_index("ix_chat_events_tenant_id", table_name="chat_events")
    op.drop_table("chat_events")
    op.drop_table("tenants")
    op.execute("DROP ROLE IF EXISTS agent_support_app")
