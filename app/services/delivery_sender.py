"""Delivery sender service.

Claims delivery_outbox rows and sends them via platform adapters.
Phase 2 implements a Telegram sandbox sender (no real API calls).
Phase 7+ will add real Discord Gateway integration.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from datetime import datetime, UTC, timedelta
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.config import settings
from app.infra.logging import logger
from app.infra.tenant_context import with_tenant_context
import app.models.platform  # noqa: F401  # Register platform tables for FK resolution.
from app.models.messaging import DeliveryOutbox, DeliveryReceipt
from app.services.rate_limits import RateLimiter, check_telegram_rate_limits
from app.services.p2_audit import emit_audit_event, SYSTEM_ACTOR


# Module-level worker ID
_WORKER_ID: str = f"delivery:{socket.gethostname()}:{id(object())}"


@dataclass(frozen=True)
class PlatformSendResult:
    """Typed platform response used by sandbox and future real senders."""

    status: str
    platform_message_id: str | None = None
    retry_after: float | None = None
    error_msg: str | None = None
    http_status: int | None = None

    @property
    def is_invalid_token(self) -> bool:
        """Return whether this response represents terminal auth failure."""
        return self.status == "invalid_token" or self.http_status in (401, 403)


def get_delivery_worker_id() -> str:
    """Return a stable worker identifier for this delivery process."""
    return _WORKER_ID


class DeliverySender:
    """Sends outbound deliveries via platform adapters.

    Lifecycle:
    1. reclaim_stale_delivery() — reset stuck processing rows to pending
    2. claim_delivery() — FOR UPDATE SKIP LOCKED claim pending rows
    3. send_delivery() — dispatch to platform-specific sender
    4. On success: create delivery_receipt + mark delivered
    5. On failure: schedule_retry() or mark_dlq()
    """

    def __init__(
        self,
        session: AsyncSession,
        worker_id: str | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """Initialize delivery sender with session and optional rate limiter."""
        self._session = session
        self._worker_id = worker_id or _WORKER_ID
        self._rate_limiter = rate_limiter or RateLimiter()

    async def get_tenants_with_pending_delivery(self) -> list[UUID]:
        """Get list of tenant IDs that have pending delivery work.

        This is a cross-tenant scan used by the worker to discover work.
        Returns unique tenant IDs with pending rows where run_after_ts <= now().
        """
        now = datetime.now(UTC)
        query = (
            select(DeliveryOutbox.tenant_id)
            .where(
                DeliveryOutbox.status == "pending",
                DeliveryOutbox.run_after_ts <= now,
                DeliveryOutbox.dead_letter == False,  # noqa: E712
            )
            .distinct()
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def claim_delivery(
        self,
        tenant_id: UUID,
        batch_size: int | None = None,
    ) -> list[DeliveryOutbox]:
        """Claim pending delivery rows using FOR UPDATE SKIP LOCKED.

        Must be called inside a transaction with tenant context set.
        Only claims rows where run_after_ts <= now() and dead_letter is false.
        Orders by created_at ASC for FIFO delivery.
        """
        size = batch_size or settings.DELIVERY_CLAIM_BATCH_SIZE
        now = datetime.now(UTC)

        # Raw SQL required for FOR UPDATE SKIP LOCKED
        claim_sql = text("""
            UPDATE delivery_outbox
            SET status = 'processing',
                worker_id = :worker_id,
                heartbeat_at = :now,
                updated_at = :now
            WHERE id IN (
                SELECT id FROM delivery_outbox
                WHERE status = 'pending'
                  AND run_after_ts <= :now
                  AND dead_letter = false
                ORDER BY created_at ASC
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id
        """)

        result = await self._session.execute(
            claim_sql,
            {
                "worker_id": self._worker_id,
                "now": now,
                "batch_size": size,
            },
        )
        claimed_ids: list[UUID] = [row[0] for row in result.fetchall()]

        if not claimed_ids:
            return []

        # Fetch full ORM objects within tenant context
        fetch_stmt = select(DeliveryOutbox).where(DeliveryOutbox.id.in_(claimed_ids))
        fetch_result = await self._session.execute(fetch_stmt)
        rows = list(fetch_result.scalars().all())

        logger.info(
            "delivery_claimed",
            tenant_id=str(tenant_id),
            count=len(rows),
            worker_id=self._worker_id,
        )
        return rows

    async def reclaim_stale_delivery(
        self,
        tenant_id: UUID,
        stale_after_seconds: int | None = None,
    ) -> int:
        """Reclaim delivery rows stuck past the stale timeout.

        Resets them to pending with a backoff delay based on current retry count.
        """
        stale_after = stale_after_seconds or settings.PROCESSING_STALE_AFTER_SECONDS
        now = datetime.now(UTC)
        stale_cutoff = now - timedelta(seconds=stale_after)

        # Fetch stale rows within tenant context
        stale_stmt = select(DeliveryOutbox).where(
            DeliveryOutbox.status == "processing",
            DeliveryOutbox.heartbeat_at < stale_cutoff,
            DeliveryOutbox.dead_letter == False,  # noqa: E712
        )
        result = await self._session.execute(stale_stmt)
        stale_rows = list(result.scalars().all())

        if not stale_rows:
            return 0

        for row in stale_rows:
            if row.retries >= settings.RETRY_MAX_ATTEMPTS:
                row.status = "dead_letter"
                row.dead_letter = True
                row.last_error = "stale_delivery_max_retries"
                row.updated_at = now
                logger.warning(
                    "delivery_dlq_stale",
                    tenant_id=str(tenant_id),
                    delivery_id=str(row.id),
                    retries=row.retries,
                )
            else:
                backoff = self._compute_backoff(row.retries)
                row.status = "pending"
                row.worker_id = None
                row.heartbeat_at = None
                row.run_after_ts = now + backoff
                row.retries += 1
                row.last_error = "stale_delivery_reclaimed"
                row.updated_at = now
                logger.info(
                    "delivery_stale_reclaimed",
                    tenant_id=str(tenant_id),
                    delivery_id=str(row.id),
                    retries=row.retries,
                    backoff_seconds=backoff.total_seconds(),
                )

        await self._session.flush()
        return len(stale_rows)

    async def send_delivery(
        self,
        delivery: DeliveryOutbox,
        tenant_id: UUID,
    ) -> DeliveryReceipt | None:
        """Send a single claimed delivery.

        Checks for existing receipt (idempotency), then dispatches to
        platform-specific sender. On success, creates a receipt and marks
        the delivery as delivered. On failure, schedules retry or moves to DLQ.

        Returns the created DeliveryReceipt, or None if skipped/failed.
        """
        now = datetime.now(UTC)

        # Idempotency check: if receipt already exists, skip
        existing_receipt_stmt = select(DeliveryReceipt).where(
            DeliveryReceipt.delivery_outbox_id == delivery.id,
            DeliveryReceipt.status == "success",
        )
        existing_receipt_result = await self._session.execute(existing_receipt_stmt)
        existing_receipt = existing_receipt_result.scalar_one_or_none()

        if existing_receipt is not None:
            logger.info(
                "delivery_already_sent",
                tenant_id=str(tenant_id),
                delivery_id=str(delivery.id),
                receipt_id=str(existing_receipt.id),
            )
            # Mark as delivered if not already
            if delivery.status != "delivered":
                delivery.status = "delivered"
                delivery.updated_at = now
                await self._session.flush()
            return existing_receipt

        # Dispatch to platform-specific sender
        try:
            if delivery.platform == "telegram":
                result = await self._send_telegram(delivery, tenant_id)
            elif delivery.platform == "discord":
                result = await self._send_discord(delivery, tenant_id)
            else:
                # Unknown platform — move to DLQ
                await self._mark_dlq(
                    delivery,
                    f"unsupported_platform:{delivery.platform}",
                    tenant_id,
                )
                return None

            send_status = result.status
            platform_message_id = result.platform_message_id
            retry_after = result.retry_after
            error_msg = result.error_msg

            if result.is_invalid_token:
                await self._mark_dlq(delivery, f"platform_auth_failed:{error_msg or send_status}", tenant_id)
                await emit_audit_event(
                    self._session,
                    tenant_id=tenant_id,
                    actor=SYSTEM_ACTOR,
                    action="delivery_platform_auth_failed",
                    metadata={
                        "delivery_id": str(delivery.id),
                        "platform": delivery.platform,
                        "status": send_status,
                        "http_status": result.http_status,
                    },
                )
                await self._session.flush()
                return None

            # Success path
            if send_status == "success":
                delivery.status = "delivered"
                delivery.updated_at = now

                # Create receipt
                receipt = DeliveryReceipt(
                    tenant_id=tenant_id,
                    delivery_outbox_id=delivery.id,
                    platform_message_id=platform_message_id,
                    status="success",
                    platform_response_json={"sandbox": True}
                    if platform_message_id and "sandbox" in platform_message_id
                    else None,
                )
                self._session.add(receipt)

                logger.info(
                    "delivery_sent",
                    tenant_id=str(tenant_id),
                    delivery_id=str(delivery.id),
                    platform=delivery.platform,
                    platform_message_id=platform_message_id,
                )
                await self._session.flush()
                return receipt
            else:
                # Transient failure — schedule retry
                error_detail = f"{send_status}:{error_msg}" if error_msg else send_status
                await self._schedule_retry(
                    delivery,
                    error_detail,
                    tenant_id,
                    retry_after=retry_after,
                )
                await self._session.flush()
                return None

        except Exception as exc:
            # Unexpected error — schedule retry
            await self._schedule_retry(delivery, str(exc), tenant_id)
            logger.error(
                "delivery_send_error",
                tenant_id=str(tenant_id),
                delivery_id=str(delivery.id),
                error=str(exc)[:200],
                exc_info=True,
            )
            return None

    async def _send_telegram(
        self,
        delivery: DeliveryOutbox,
        tenant_id: UUID,
    ) -> PlatformSendResult:
        """Send via Telegram (Phase 2 sandbox — no real API calls).

        Checks rate limits, then simulates a successful send.
        Phase 7+ will replace this with real Telegram Bot API calls.

        Returns:
            PlatformSendResult with status, platform message id, retry delay, and error.
        """
        # Extract chat_id from delivery metadata or channel
        chat_id = delivery.metadata_json.get("external_channel_id") or str(delivery.channel_id)
        is_group = delivery.metadata_json.get("chat_type") in ("group", "supergroup")

        # Check rate limits
        allowed, wait_seconds = check_telegram_rate_limits(chat_id, is_group=is_group, limiter=self._rate_limiter)
        if not allowed:
            return PlatformSendResult(
                "rate_limited", retry_after=wait_seconds, error_msg=f"rate_limit_wait:{wait_seconds:.2f}s"
            )

        # Sandbox send — simulate success
        # Phase 7+ will call: POST https://api.telegram.org/bot{token}/sendMessage
        sandbox_message_id = f"tg:sandbox:{delivery.id}"

        return PlatformSendResult("success", platform_message_id=sandbox_message_id)

    async def _send_discord(
        self,
        delivery: DeliveryOutbox,
        tenant_id: UUID,
    ) -> PlatformSendResult:
        """Send via Discord (Phase 7+ placeholder).

        Phase 2 does not implement real Discord sending.

        Returns:
            PlatformSendResult with retry metadata.
        """
        return PlatformSendResult("rate_limited", retry_after=3600.0, error_msg="discord_sender_not_implemented")

    async def _schedule_retry(
        self,
        delivery: DeliveryOutbox,
        error: str,
        tenant_id: UUID,
        retry_after: float | None = None,
    ) -> None:
        """Schedule a retry with backoff or move to DLQ.

        If retries >= RETRY_MAX_ATTEMPTS, the row is moved to dead_letter.
        Otherwise, run_after_ts is set to now + backoff (or retry_after if provided).
        """
        now = datetime.now(UTC)

        if delivery.retries >= settings.RETRY_MAX_ATTEMPTS:
            await self._mark_dlq(delivery, error, tenant_id)
            await emit_audit_event(
                self._session,
                tenant_id=tenant_id,
                actor=SYSTEM_ACTOR,
                action="delivery_dlq",
                metadata={
                    "delivery_id": str(delivery.id),
                    "platform": delivery.platform,
                    "error": error[:500],
                    "retries": delivery.retries,
                },
            )
            return

        if retry_after is not None:
            backoff = timedelta(seconds=retry_after)
        else:
            backoff = self._compute_backoff(delivery.retries)

        delivery.status = "pending"
        delivery.worker_id = None
        delivery.heartbeat_at = None
        delivery.run_after_ts = now + backoff
        delivery.retries += 1
        delivery.last_error = error[:1000]
        delivery.updated_at = now

        backoff_seconds = backoff.total_seconds()
        logger.info(
            "delivery_retry_scheduled",
            tenant_id=str(tenant_id),
            delivery_id=str(delivery.id),
            retries=delivery.retries,
            backoff_seconds=backoff_seconds,
        )
        await emit_audit_event(
            self._session,
            tenant_id=tenant_id,
            actor=SYSTEM_ACTOR,
            action="delivery_retry_scheduled",
            metadata={
                "delivery_id": str(delivery.id),
                "platform": delivery.platform,
                "error": error[:500],
                "retries": delivery.retries,
                "backoff_seconds": backoff_seconds,
            },
        )

    async def _mark_dlq(
        self,
        delivery: DeliveryOutbox,
        error: str,
        tenant_id: UUID,
    ) -> None:
        """Mark a delivery as dead letter."""
        now = datetime.now(UTC)
        delivery.status = "dead_letter"
        delivery.dead_letter = True
        delivery.last_error = error[:1000]
        delivery.updated_at = now

        logger.warning(
            "delivery_dlq",
            tenant_id=str(tenant_id),
            delivery_id=str(delivery.id),
            retries=delivery.retries,
            error=error[:200],
        )

    def _compute_backoff(self, retries: int) -> timedelta:
        """Compute exponential backoff delay for a retry.

        backoff = min(base * 2^retries, max_seconds)
        """
        base = settings.RETRY_BACKOFF_BASE_SECONDS
        cap = settings.RETRY_BACKOFF_MAX_SECONDS
        delay = min(base * (2**retries), cap)
        return timedelta(seconds=delay)

    async def run_cycle(self, tenant_id: UUID) -> dict[str, int]:
        """Run one full delivery cycle for a tenant.

        1. Reclaim stale rows
        2. Claim pending batch
        3. Send each claimed delivery

        Returns a summary dict with counts.
        """
        stats: dict[str, int] = {"reclaimed": 0, "claimed": 0, "sent": 0, "failed": 0}

        async with with_tenant_context(self._session, tenant_id):
            # Phase 1: reclaim stale
            stats["reclaimed"] = await self.reclaim_stale_delivery(tenant_id)

            # Phase 2: claim + send
            claimed = await self.claim_delivery(tenant_id)
            stats["claimed"] = len(claimed)

            for delivery in claimed:
                receipt = await self.send_delivery(delivery, tenant_id)
                if receipt is not None and receipt.status == "success":
                    stats["sent"] += 1
                else:
                    stats["failed"] += 1

            await self._session.commit()

        return stats
