"""Trusted platform ingest service.

Centralizes tenant/platform/channel resolution and atomic chat_events +
processing_outbox creation for both Telegram webhook and generic adapter ingest.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, UTC
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.platform import AdapterCredential, PlatformChannel, TenantPlatform
from app.models.messaging import ChatEvent, ProcessingOutbox
from app.schemas.adapter import (
    NormalizedInboundEvent,
    Platform,
)
from app.services.p2_audit import emit_audit_event, SYSTEM_ACTOR


# --- Service errors ---


class IngestError(Exception):
    """Base error for platform ingest operations."""

    def __init__(self, message: str, *, audit_action: str | None = None) -> None:
        """Initialize ingest error with message and optional audit action."""
        super().__init__(message)
        self.audit_action = audit_action


class SecretMismatchError(IngestError):
    """Webhook secret verification failed."""

    def __init__(self, tenant_id: UUID | None = None) -> None:
        """Initialize secret mismatch error with optional tenant context."""
        super().__init__("Webhook secret mismatch", audit_action="webhook_secret_rejected")
        self.tenant_id = tenant_id


class UnknownPlatformMappingError(IngestError):
    """No active tenant_platform found for the given criteria."""

    def __init__(self, *, platform: str, tenant_id: UUID | None = None) -> None:
        """Initialize unknown platform error with platform name and optional tenant context."""
        super().__init__(
            f"Unknown platform mapping for {platform}",
            audit_action="unknown_platform_mapping",
        )
        self.platform = platform
        self.tenant_id = tenant_id


class DisabledPlatformError(IngestError):
    """Platform integration is disabled."""

    def __init__(self, *, platform: str, tenant_id: UUID) -> None:
        """Initialize with platform and tenant context."""
        super().__init__(
            f"Platform {platform} is disabled for tenant",
            audit_action="disabled_platform_rejected",
        )
        self.platform = platform
        self.tenant_id = tenant_id


class UnknownChannelError(IngestError):
    """No active platform_channel found for the external channel ID."""

    def __init__(self, *, external_channel_id: str, tenant_id: UUID) -> None:
        """Initialize with external channel ID and tenant context."""
        super().__init__(
            "Unknown channel",
            audit_action="unknown_channel_rejected",
        )
        self.external_channel_id = external_channel_id
        self.tenant_id = tenant_id


class DisabledChannelError(IngestError):
    """Platform channel is disabled."""

    def __init__(self, *, external_channel_id: str, tenant_id: UUID) -> None:
        """Initialize with external channel ID and tenant context."""
        super().__init__(
            "Channel is disabled",
            audit_action="disabled_channel_rejected",
        )
        self.external_channel_id = external_channel_id
        self.tenant_id = tenant_id


class InvalidAdapterCredentialError(IngestError):
    """Adapter credential is missing, invalid, disabled, or expired."""

    def __init__(self, *, reason: str = "invalid") -> None:
        """Initialize with failure reason."""
        super().__init__(
            f"Invalid adapter credential: {reason}",
            audit_action="invalid_adapter_credential",
        )
        self.reason = reason


class ScopeMismatchError(IngestError):
    """Adapter principal scope does not cover the requested channel/platform."""

    def __init__(self) -> None:
        """Initialize scope mismatch error."""
        super().__init__("Scope mismatch", audit_action="scope_mismatch_rejected")


class DuplicateAcceptedError(IngestError):
    """Duplicate inbound event accepted idempotently."""

    def __init__(self, *, existing_event_id: UUID) -> None:
        """Initialize with existing event ID."""
        super().__init__("Duplicate event accepted", audit_action="duplicate_accepted")
        self.existing_event_id = existing_event_id


# --- Helpers ---


def _hash_secret(secret: str) -> str:
    """Hash a webhook secret using SHA-256."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# --- Ingest service ---


class PlatformIngestService:
    """Handles trusted ingest for all inbound platform paths."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with database session."""
        self._session = session

    async def verify_webhook_secret(
        self,
        *,
        tenant_id: UUID,
        platform: Platform,
        secret_token: str,
    ) -> TenantPlatform:
        """Verify a webhook secret against the stored hash.

        Resolves the TenantPlatform via (tenant_id, platform), then verifies
        the secret hash using constant-time comparison.

        Returns the active TenantPlatform on success.
        """
        result = await self._session.execute(
            select(TenantPlatform).where(
                TenantPlatform.tenant_id == tenant_id,
                TenantPlatform.platform == platform.value,
                TenantPlatform.status == "active",
            )
        )
        tenant_platform = result.scalar_one_or_none()

        if tenant_platform is None:
            raise UnknownPlatformMappingError(platform=platform.value, tenant_id=tenant_id)

        if not tenant_platform.webhook_secret_hash:
            logger.warning("webhook_secret_not_configured", tenant_id=str(tenant_id), platform=platform.value)
            await emit_audit_event(
                self._session,
                tenant_id=tenant_id,
                actor=SYSTEM_ACTOR,
                action="webhook_secret_not_configured",
                metadata={"platform": platform.value},
            )
            raise SecretMismatchError(tenant_id=tenant_id)

        incoming_hash = _hash_secret(secret_token)
        if not _constant_time_compare(incoming_hash, tenant_platform.webhook_secret_hash):
            await emit_audit_event(
                self._session,
                tenant_id=tenant_id,
                actor=SYSTEM_ACTOR,
                action="webhook_secret_rejected",
                metadata={"platform": platform.value},
            )
            raise SecretMismatchError(tenant_id=tenant_id)

        return tenant_platform

    async def resolve_channel(
        self,
        *,
        tenant_platform_id: UUID,
        external_channel_id: str,
        external_thread_id: str | None = None,
    ) -> PlatformChannel:
        """Resolve an active platform channel from external IDs.

        Tries exact match on (tenant_platform_id, external_channel_id, external_thread_id).
        Falls back to (tenant_platform_id, external_channel_id, NULL thread) if thread not found.
        """
        # Try exact match first (with thread)
        result = await self._session.execute(
            select(PlatformChannel).where(
                PlatformChannel.tenant_platform_id == tenant_platform_id,
                PlatformChannel.external_channel_id == external_channel_id,
                PlatformChannel.external_thread_id == external_thread_id,
                PlatformChannel.status == "active",
            )
        )
        channel = result.scalar_one_or_none()
        if channel is not None:
            return channel

        # If we had a thread_id, try without it (channel-level mapping)
        if external_thread_id is not None:
            result = await self._session.execute(
                select(PlatformChannel).where(
                    PlatformChannel.tenant_platform_id == tenant_platform_id,
                    PlatformChannel.external_channel_id == external_channel_id,
                    PlatformChannel.external_thread_id.is_(None),
                    PlatformChannel.status == "active",
                )
            )
            channel = result.scalar_one_or_none()
            if channel is not None:
                return channel

        # Check if channel exists but is disabled
        result = await self._session.execute(
            select(PlatformChannel).where(
                PlatformChannel.tenant_platform_id == tenant_platform_id,
                PlatformChannel.external_channel_id == external_channel_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None and existing.status != "active":
            raise DisabledChannelError(
                external_channel_id=external_channel_id,
                tenant_id=existing.tenant_id,
            )

        raise UnknownChannelError(
            external_channel_id=external_channel_id,
            tenant_id=existing.tenant_id if existing else UUID(int=0),
        )

    async def ingest_event(
        self,
        *,
        tenant_id: UUID,
        event: NormalizedInboundEvent,
        channel: PlatformChannel,
    ) -> tuple[ChatEvent, ProcessingOutbox] | DuplicateAcceptedError:
        """Persist chat_events + processing_outbox atomically.

        Returns (chat_event, processing_outbox) on success, or
        DuplicateAcceptedError if the event was already ingested.
        """
        chat_event = ChatEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            platform=event.platform.value,
            external_message_id=event.external_message_id,
            direction=event.direction.value,
            channel_id=channel.id,
            thread_id=channel.id if event.external_thread_id else None,
            user_id=event.external_user_id,
            message_type=event.message_type.value,
            text_preview=event.text_preview,
            metadata_json=event.metadata,
        )

        processing_row = ProcessingOutbox(
            id=uuid4(),
            tenant_id=tenant_id,
            chat_event_id=chat_event.id,
            status="pending",
            run_after_ts=datetime.now(UTC),
            retries=0,
            dead_letter=False,
        )

        try:
            self._session.add(chat_event)
            self._session.add(processing_row)
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            # Duplicate — fetch existing event
            result = await self._session.execute(
                select(ChatEvent).where(
                    ChatEvent.tenant_id == tenant_id,
                    ChatEvent.platform == event.platform.value,
                    ChatEvent.external_message_id == event.external_message_id,
                    ChatEvent.direction == event.direction.value,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                return DuplicateAcceptedError(existing_event_id=existing.id)
            # Re-raise if the integrity error was not a duplicate
            raise

        # Best-effort NOTIFY for outbox workers
        try:
            await self._session.execute(text("NOTIFY outbox_new"))
        except Exception:
            logger.debug("notify_outbox_new_failed", exc_info=True)

        # Audit the successful ingest
        await emit_audit_event(
            self._session,
            tenant_id=tenant_id,
            actor=SYSTEM_ACTOR,
            action="event_ingested",
            metadata={
                "event_id": str(chat_event.id),
                "platform": event.platform.value,
                "message_type": event.message_type.value,
                "external_message_id": event.external_message_id,
            },
        )

        return (chat_event, processing_row)


async def resolve_adapter_credential(
    session: AsyncSession,
    *,
    credential_raw: str,
) -> AdapterCredential:
    """Resolve and validate an adapter credential from its raw secret.

    Looks up by prefix, then verifies the full hash.
    Returns the active AdapterCredential on success.
    """
    # Extract prefix (first 8 chars)
    if len(credential_raw) < 8:
        raise InvalidAdapterCredentialError(reason="too_short")

    prefix = credential_raw[:8]
    credential_hash = hashlib.sha256(credential_raw.encode("utf-8")).hexdigest()

    result = await session.execute(
        select(AdapterCredential).where(
            AdapterCredential.credential_prefix == prefix,
        )
    )
    candidates = result.scalars().all()

    for candidate in candidates:
        if _constant_time_compare(credential_hash, candidate.credential_hash):
            # Verify status
            if candidate.status != "active":
                raise InvalidAdapterCredentialError(reason=candidate.status)
            # Verify not expired
            if candidate.expires_at and candidate.expires_at < datetime.now(UTC):
                raise InvalidAdapterCredentialError(reason="expired")
            return candidate

    raise InvalidAdapterCredentialError(reason="not_found")
