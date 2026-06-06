"""P2 platform ingest and outbox pattern.

Revision ID: a3f5c8e12d47
Revises: 7b3d2e8f9a10
Create Date: 2026-06-06 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a3f5c8e12d47"
down_revision: Union[str, Sequence[str], None] = "7b3d2e8f9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_OWNED_TABLES = (
    "tenant_platforms",
    "adapter_credentials",
    "platform_channels",
    "chat_events",
    "processing_outbox",
    "delivery_outbox",
    "delivery_receipts",
)


def _create_rls_policy(table_name: str) -> None:
    """Enable and force RLS on tenant-owned tables."""
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
    # tenant_platforms: tenant's platform integrations
    op.create_table(
        "tenant_platforms",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("external_workspace_id", sa.String(), nullable=True),
        sa.Column("webhook_secret_hash", sa.String(), nullable=True),
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("platform IN ('telegram','discord')", name="ck_tenant_platforms_platform"),
        sa.CheckConstraint("status IN ('active','disabled','suspended')", name="ck_tenant_platforms_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "platform", "external_workspace_id", name="uq_tenant_platforms_tenant_platform_workspace"
        ),
    )
    op.create_index("idx_tenant_platforms_tenant", "tenant_platforms", ["tenant_id"], unique=False)

    # adapter_credentials: credentials for adapter principal auth
    op.create_table(
        "adapter_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("credential_hash", sa.String(), nullable=False),
        sa.Column("credential_prefix", sa.String(), nullable=False),
        sa.Column("credential_fingerprint", sa.String(), nullable=False),
        sa.Column(
            "allowed_channel_patterns",
            postgresql.ARRAY(sa.String()),
            server_default=sa.text("ARRAY[]::text[]"),
            nullable=False,
        ),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), server_default=sa.text("ARRAY[]::text[]"), nullable=False),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("platform IN ('telegram','discord')", name="ck_adapter_credentials_platform"),
        sa.CheckConstraint("status IN ('active','revoked','expired')", name="ck_adapter_credentials_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_adapter_credentials_tenant", "adapter_credentials", ["tenant_id"], unique=False)
    op.create_index("idx_adapter_credentials_prefix", "adapter_credentials", ["credential_prefix"], unique=False)

    # platform_channels: channels/threads within a platform
    op.create_table(
        "platform_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_platform_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_channel_id", sa.String(), nullable=False),
        sa.Column("external_thread_id", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active','disabled','archived')", name="ck_platform_channels_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_platform_id"], ["tenant_platforms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_platform_id",
            "external_channel_id",
            "external_thread_id",
            name="uq_platform_channels_platform_channel_thread",
        ),
    )
    op.create_index("idx_platform_channels_tenant", "platform_channels", ["tenant_id"], unique=False)

    # chat_events: inbound events (idempotent)
    op.create_table(
        "chat_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("external_message_id", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("text_preview", sa.String(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("platform IN ('telegram','discord')", name="ck_chat_events_platform"),
        sa.CheckConstraint("direction IN ('inbound','outbound')", name="ck_chat_events_direction"),
        sa.CheckConstraint(
            "message_type IN ('text','command','media','system','edited')", name="ck_chat_events_message_type"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["platform_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "platform",
            "external_message_id",
            "direction",
            name="uq_chat_events_tenant_platform_message_direction",
        ),
    )
    op.create_index("idx_chat_events_tenant_channel", "chat_events", ["tenant_id", "channel_id"], unique=False)

    # processing_outbox: work queue for processing
    op.create_table(
        "processing_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chat_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("run_after_ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retries", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("dead_letter", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','processing','done','failed','dead_letter')", name="ck_processing_outbox_status"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_event_id"], ["chat_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_processing_outbox_tenant", "processing_outbox", ["tenant_id"], unique=False)
    op.create_index(
        "idx_processing_outbox_pending",
        "processing_outbox",
        ["status", "run_after_ts"],
        postgresql_where=sa.text("status = 'pending' AND dead_letter = false"),
    )

    # delivery_outbox: outbound delivery queue
    op.create_table(
        "delivery_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("processing_outbox_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("text_content", sa.String(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("run_after_ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retries", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("dead_letter", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("platform IN ('telegram','discord')", name="ck_delivery_outbox_platform"),
        sa.CheckConstraint(
            "action IN ('send_message','edit_message','delete_message')", name="ck_delivery_outbox_action"
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','delivered','failed','dead_letter')", name="ck_delivery_outbox_status"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["processing_outbox_id"], ["processing_outbox.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["platform_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_delivery_outbox_tenant_idempotency"),
    )
    op.create_index("idx_delivery_outbox_tenant", "delivery_outbox", ["tenant_id"], unique=False)
    op.create_index(
        "idx_delivery_outbox_pending",
        "delivery_outbox",
        ["status", "run_after_ts"],
        postgresql_where=sa.text("status = 'pending' AND dead_letter = false"),
    )

    # delivery_receipts: delivery confirmations
    op.create_table(
        "delivery_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_outbox_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform_message_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("platform_response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('success','failed','timeout','rate_limited')", name="ck_delivery_receipts_status"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delivery_outbox_id"], ["delivery_outbox.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_delivery_receipts_tenant", "delivery_receipts", ["tenant_id"], unique=False)
    op.create_index("idx_delivery_receipts_delivery", "delivery_receipts", ["delivery_outbox_id"], unique=False)

    # Enable RLS on all tenant-owned tables
    for table_name in TENANT_OWNED_TABLES:
        _create_rls_policy(table_name)


def downgrade() -> None:
    """Downgrade schema."""
    for table_name in reversed(TENANT_OWNED_TABLES):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}"))
        op.execute(sa.text(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"))
    op.drop_index("idx_delivery_receipts_delivery", table_name="delivery_receipts")
    op.drop_index("idx_delivery_receipts_tenant", table_name="delivery_receipts")
    op.drop_table("delivery_receipts")
    op.drop_index("idx_delivery_outbox_pending", table_name="delivery_outbox")
    op.drop_index("idx_delivery_outbox_tenant", table_name="delivery_outbox")
    op.drop_table("delivery_outbox")
    op.drop_index("idx_processing_outbox_pending", table_name="processing_outbox")
    op.drop_index("idx_processing_outbox_tenant", table_name="processing_outbox")
    op.drop_table("processing_outbox")
    op.drop_index("idx_chat_events_tenant_channel", table_name="chat_events")
    op.drop_table("chat_events")
    op.drop_index("idx_platform_channels_tenant", table_name="platform_channels")
    op.drop_table("platform_channels")
    op.drop_index("idx_adapter_credentials_prefix", table_name="adapter_credentials")
    op.drop_index("idx_adapter_credentials_tenant", table_name="adapter_credentials")
    op.drop_table("adapter_credentials")
    op.drop_index("idx_tenant_platforms_tenant", table_name="tenant_platforms")
    op.drop_table("tenant_platforms")
