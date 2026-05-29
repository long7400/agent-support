"""chat event idempotency

Revision ID: 0004_chat_event_idempotency
Revises: 0003_tenant_platforms
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_chat_event_idempotency"
down_revision: str | None = "0003_tenant_platforms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_events",
        sa.Column("direction", sa.String(length=32), nullable=False, server_default="inbound"),
    )
    op.add_column("chat_events", sa.Column("thread_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_chat_events_tenant_platform_channel_message_direction",
        "chat_events",
        ["tenant_id", "platform", "channel_id", "message_id", "direction"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_chat_events_tenant_platform_channel_message_direction",
        "chat_events",
        type_="unique",
    )
    op.drop_column("chat_events", "thread_id")
    op.drop_column("chat_events", "direction")
