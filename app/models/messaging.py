"""Messaging and outbox persistence models."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

MESSAGE_DIRECTIONS = ("inbound", "outbound")
MESSAGE_TYPES = ("text", "command", "media", "system", "edited")
PROCESSING_STATUSES = ("pending", "processing", "done", "failed", "dead_letter")
DELIVERY_ACTIONS = ("send_message", "edit_message", "delete_message")
DELIVERY_STATUSES = ("pending", "processing", "delivered", "failed", "dead_letter")
RECEIPT_STATUSES = ("success", "failed", "timeout", "rate_limited")


class ChatEvent(TimestampMixin, Base):
    """Inbound/outbound chat event (idempotent)."""

    __tablename__ = "chat_events"
    __table_args__ = (
        CheckConstraint("platform IN ('telegram','discord')", name="ck_chat_events_platform"),
        CheckConstraint("direction IN ('inbound','outbound')", name="ck_chat_events_direction"),
        CheckConstraint(
            "message_type IN ('text','command','media','system','edited')", name="ck_chat_events_message_type"
        ),
        UniqueConstraint(
            "tenant_id",
            "platform",
            "external_message_id",
            "direction",
            name="uq_chat_events_tenant_platform_message_direction",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    external_message_id: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    channel_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("platform_channels.id"), nullable=False)
    thread_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    message_type: Mapped[str] = mapped_column(String, nullable=False)
    text_preview: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ProcessingOutbox(TimestampMixin, Base):
    """Work queue for processing inbound events."""

    __tablename__ = "processing_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','done','failed','dead_letter')", name="ck_processing_outbox_status"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    chat_event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("chat_events.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    run_after_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    worker_id: Mapped[str | None] = mapped_column(String, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    dead_letter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class DeliveryOutbox(TimestampMixin, Base):
    """Outbound delivery queue."""

    __tablename__ = "delivery_outbox"
    __table_args__ = (
        CheckConstraint("platform IN ('telegram','discord')", name="ck_delivery_outbox_platform"),
        CheckConstraint(
            "action IN ('send_message','edit_message','delete_message')", name="ck_delivery_outbox_action"
        ),
        CheckConstraint(
            "status IN ('pending','processing','delivered','failed','dead_letter')", name="ck_delivery_outbox_status"
        ),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_delivery_outbox_tenant_idempotency"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    processing_outbox_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("processing_outbox.id"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String, nullable=False)
    channel_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("platform_channels.id"), nullable=False)
    thread_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    text_content: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    agent_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    run_after_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    worker_id: Mapped[str | None] = mapped_column(String, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    dead_letter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class DeliveryReceipt(TimestampMixin, Base):
    """Delivery confirmation after platform send."""

    __tablename__ = "delivery_receipts"
    __table_args__ = (
        CheckConstraint("status IN ('success','failed','timeout','rate_limited')", name="ck_delivery_receipts_status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    delivery_outbox_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("delivery_outbox.id"), nullable=False
    )
    platform_message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    platform_response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
