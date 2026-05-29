"""stream outbox

Revision ID: 0005_stream_outbox
Revises: 0004_chat_event_idempotency
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_stream_outbox"
down_revision: str | None = "0004_chat_event_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stream_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chat_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stream_name", sa.String(length=512), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("redis_message_id", sa.String(length=128), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
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
            "chat_event_id",
            "stream_name",
            name="uq_stream_outbox_chat_event_stream",
        ),
    )
    op.create_index("ix_stream_outbox_tenant_id", "stream_outbox", ["tenant_id"])
    op.create_index("ix_stream_outbox_status", "stream_outbox", ["status"])
    op.create_index("ix_stream_outbox_chat_event_id", "stream_outbox", ["chat_event_id"])

    op.execute("ALTER TABLE stream_outbox ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE stream_outbox FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_stream_outbox ON stream_outbox
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON stream_outbox TO agent_support_app")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON stream_outbox FROM agent_support_app")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_stream_outbox ON stream_outbox")
    op.drop_index("ix_stream_outbox_chat_event_id", table_name="stream_outbox")
    op.drop_index("ix_stream_outbox_status", table_name="stream_outbox")
    op.drop_index("ix_stream_outbox_tenant_id", table_name="stream_outbox")
    op.drop_table("stream_outbox")
