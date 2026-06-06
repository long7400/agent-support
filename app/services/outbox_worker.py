"""Processing outbox worker operations.

Implements SKIP LOCKED claim, stale reclaim, stub delivery creation,
retry/backoff, and dead-letter queue for the processing outbox.

Phase 2 stub processing creates a delivery_outbox row (echo reply).
Phase 3+ will replace the stub with LangGraph agent execution.
"""

from __future__ import annotations

import socket
from datetime import datetime, UTC, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.tenant_context import with_tenant_context
import app.models.platform  # noqa: F401  # Register platform tables for FK resolution.
from app.models.messaging import ChatEvent, DeliveryOutbox, ProcessingOutbox
from app.services.p2_audit import emit_audit_event, SYSTEM_ACTOR


# Module-level worker ID (stable for the process lifetime)
_WORKER_ID: str = f"{socket.gethostname()}:{id(object())}"


def get_worker_id() -> str:
    """Return a stable worker identifier for this process."""
    return _WORKER_ID


def compute_backoff(
    retries: int,
    base_seconds: int | None = None,
    max_seconds: int | None = None,
) -> timedelta:
    """Compute exponential backoff delay for a retry.

    backoff = min(base * 2^retries, max_seconds)
    """
    base = base_seconds or settings.RETRY_BACKOFF_BASE_SECONDS
    cap = max_seconds or settings.RETRY_BACKOFF_MAX_SECONDS
    delay = min(base * (2**retries), cap)
    return timedelta(seconds=delay)


class ProcessingOutboxWorker:
    """Processes rows from the processing_outbox table.

    Lifecycle:
    1. reclaim_stale() — reset stuck processing rows to pending
    2. claim_batch() — FOR UPDATE SKIP LOCKED claim pending rows
    3. process_row() — stub: create delivery_outbox + mark done
    4. On failure: schedule_retry() or mark_dlq()
    """

    def __init__(self, session: AsyncSession, worker_id: str | None = None) -> None:
        """Initialize processing outbox worker with session."""
        self._session = session
        self._worker_id = worker_id or _WORKER_ID

    async def get_tenants_with_pending_processing(self) -> list[UUID]:
        """Get list of tenant IDs that have pending processing work.

        This is a cross-tenant scan used by the worker to discover work.
        Returns unique tenant IDs with pending rows where run_after_ts <= now().
        """
        now = datetime.now(UTC)
        query = (
            select(ProcessingOutbox.tenant_id)
            .where(
                ProcessingOutbox.status == "pending",
                ProcessingOutbox.run_after_ts <= now,
                ProcessingOutbox.dead_letter == False,  # noqa: E712
            )
            .distinct()
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def claim_batch(
        self,
        tenant_id: UUID,
        batch_size: int | None = None,
    ) -> list[ProcessingOutbox]:
        """Claim pending processing rows using FOR UPDATE SKIP LOCKED.

        Must be called inside a transaction with tenant context set.
        Only claims rows where run_after_ts <= now() and dead_letter is false.
        Orders by created_at ASC for FIFO processing.
        """
        size = batch_size or settings.PROCESSING_CLAIM_BATCH_SIZE
        now = datetime.now(UTC)

        # Raw SQL required for FOR UPDATE SKIP LOCKED
        claim_sql = text("""
            UPDATE processing_outbox
            SET status = 'processing',
                worker_id = :worker_id,
                heartbeat_at = :now,
                updated_at = :now
            WHERE id IN (
                SELECT id FROM processing_outbox
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
        fetch_stmt = select(ProcessingOutbox).where(ProcessingOutbox.id.in_(claimed_ids))
        fetch_result = await self._session.execute(fetch_stmt)
        rows = list(fetch_result.scalars().all())

        logger.info(
            "processing_claimed",
            tenant_id=str(tenant_id),
            count=len(rows),
            worker_id=self._worker_id,
        )
        return rows

    async def reclaim_stale(
        self,
        tenant_id: UUID,
        stale_after_seconds: int | None = None,
    ) -> int:
        """Reclaim processing rows stuck past the stale timeout.

        Resets them to pending with a backoff delay based on current retry count.
        """
        stale_after = stale_after_seconds or settings.PROCESSING_STALE_AFTER_SECONDS
        now = datetime.now(UTC)
        stale_cutoff = now - timedelta(seconds=stale_after)

        # Fetch stale rows within tenant context
        stale_stmt = select(ProcessingOutbox).where(
            ProcessingOutbox.status == "processing",
            ProcessingOutbox.heartbeat_at < stale_cutoff,
            ProcessingOutbox.dead_letter == False,  # noqa: E712
        )
        result = await self._session.execute(stale_stmt)
        stale_rows = list(result.scalars().all())

        if not stale_rows:
            return 0

        for row in stale_rows:
            if row.retries >= settings.RETRY_MAX_ATTEMPTS:
                row.status = "dead_letter"
                row.dead_letter = True
                row.last_error = "stale_processing_max_retries"
                row.updated_at = now
                logger.warning(
                    "processing_dlq_stale",
                    tenant_id=str(tenant_id),
                    outbox_id=str(row.id),
                    retries=row.retries,
                )
            else:
                backoff = compute_backoff(row.retries)
                row.status = "pending"
                row.worker_id = None
                row.heartbeat_at = None
                row.run_after_ts = now + backoff
                row.retries += 1
                row.last_error = "stale_processing_reclaimed"
                row.updated_at = now
                logger.info(
                    "processing_stale_reclaimed",
                    tenant_id=str(tenant_id),
                    outbox_id=str(row.id),
                    retries=row.retries,
                    backoff_seconds=backoff.total_seconds(),
                )

        await self._session.flush()
        return len(stale_rows)

    async def process_row(
        self,
        row: ProcessingOutbox,
        tenant_id: UUID,
    ) -> DeliveryOutbox | None:
        """Process a single claimed row (Phase 2 stub).

        Stub behavior: creates a delivery_outbox row echoing the inbound
        text as a send_message, then marks the processing row as done.

        Returns the created DeliveryOutbox row, or None if the chat event
        cannot be resolved.
        """
        now = datetime.now(UTC)

        # Fetch the associated chat event
        event_stmt = select(ChatEvent).where(ChatEvent.id == row.chat_event_id)
        event_result = await self._session.execute(event_stmt)
        chat_event = event_result.scalar_one_or_none()

        if chat_event is None:
            logger.error(
                "processing_missing_chat_event",
                tenant_id=str(tenant_id),
                outbox_id=str(row.id),
                chat_event_id=str(row.chat_event_id),
            )
            await self._mark_failed(row, "chat_event_not_found", tenant_id)
            return None

        # Build deterministic idempotency key for outbound delivery
        idempotency_key = f"p2:echo:{chat_event.id}"

        # Determine outbound action
        action = "send_message"
        text_content = chat_event.text_preview or ""

        # Build delivery metadata (bounded, no raw payload)
        delivery_metadata: dict[str, Any] = {
            "source": "processing_stub",
            "inbound_message_type": chat_event.message_type,
        }

        # Check for existing delivery (idempotency)
        existing_stmt = select(DeliveryOutbox).where(
            DeliveryOutbox.tenant_id == tenant_id,
            DeliveryOutbox.idempotency_key == idempotency_key,
        )
        existing_result = await self._session.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing is not None:
            # Already created — mark processing as done without duplicate
            row.status = "done"
            row.heartbeat_at = now
            row.updated_at = now
            logger.info(
                "processing_delivery_exists",
                tenant_id=str(tenant_id),
                outbox_id=str(row.id),
                delivery_id=str(existing.id),
            )
            return existing

        # Create delivery_outbox row
        delivery = DeliveryOutbox(
            tenant_id=tenant_id,
            processing_outbox_id=row.id,
            platform=chat_event.platform,
            channel_id=chat_event.channel_id,
            thread_id=chat_event.thread_id,
            action=action,
            text_content=text_content,
            metadata_json=delivery_metadata,
            idempotency_key=idempotency_key,
            status="pending",
            run_after_ts=now,
            retries=0,
            dead_letter=False,
        )
        self._session.add(delivery)

        # Mark processing as done
        row.status = "done"
        row.heartbeat_at = now
        row.updated_at = now

        await self._session.flush()

        logger.info(
            "processing_done",
            tenant_id=str(tenant_id),
            outbox_id=str(row.id),
            delivery_id=str(delivery.id),
            action=action,
        )
        return delivery

    async def schedule_retry(
        self,
        row: ProcessingOutbox,
        error: str,
        tenant_id: UUID,
    ) -> None:
        """Schedule a retry with exponential backoff or move to DLQ.

        If retries >= RETRY_MAX_ATTEMPTS, the row is moved to dead_letter.
        Otherwise, run_after_ts is set to now + backoff and retries is incremented.
        """
        now = datetime.now(UTC)

        if row.retries >= settings.RETRY_MAX_ATTEMPTS:
            row.status = "dead_letter"
            row.dead_letter = True
            row.last_error = error[:1000]  # bounded
            row.updated_at = now
            logger.warning(
                "processing_dlq",
                tenant_id=str(tenant_id),
                outbox_id=str(row.id),
                retries=row.retries,
                error=error[:200],
            )
            await emit_audit_event(
                self._session,
                tenant_id=tenant_id,
                actor=SYSTEM_ACTOR,
                action="processing_dlq",
                metadata={
                    "outbox_id": str(row.id),
                    "error": error[:500],
                    "retries": row.retries,
                },
            )
        else:
            backoff = compute_backoff(row.retries)
            row.status = "pending"
            row.worker_id = None
            row.heartbeat_at = None
            row.run_after_ts = now + backoff
            row.retries += 1
            row.last_error = error[:1000]
            row.updated_at = now
            backoff_seconds = backoff.total_seconds()
            logger.info(
                "processing_retry_scheduled",
                tenant_id=str(tenant_id),
                outbox_id=str(row.id),
                retries=row.retries,
                backoff_seconds=backoff_seconds,
            )
            await emit_audit_event(
                self._session,
                tenant_id=tenant_id,
                actor=SYSTEM_ACTOR,
                action="processing_retry_scheduled",
                metadata={
                    "outbox_id": str(row.id),
                    "error": error[:500],
                    "retries": row.retries,
                    "backoff_seconds": backoff_seconds,
                },
            )

        await self._session.flush()

    async def _mark_failed(
        self,
        row: ProcessingOutbox,
        error: str,
        tenant_id: UUID,
    ) -> None:
        """Mark a row as failed (terminal, not retryable)."""
        now = datetime.now(UTC)
        row.status = "failed"
        row.last_error = error[:1000]
        row.updated_at = now
        await self._session.flush()

        logger.error(
            "processing_failed",
            tenant_id=str(tenant_id),
            outbox_id=str(row.id),
            error=error[:200],
        )

    async def run_cycle(self, tenant_id: UUID) -> dict[str, int]:
        """Run one full processing cycle for a tenant.

        1. Reclaim stale rows
        2. Claim pending batch
        3. Process each claimed row

        Returns a summary dict with counts.
        """
        stats: dict[str, int] = {"reclaimed": 0, "claimed": 0, "processed": 0, "failed": 0}

        async with with_tenant_context(self._session, tenant_id):
            # Phase 1: reclaim stale
            stats["reclaimed"] = await self.reclaim_stale(tenant_id)

            # Phase 2: claim + process
            claimed = await self.claim_batch(tenant_id)
            stats["claimed"] = len(claimed)

            for row in claimed:
                try:
                    result = await self.process_row(row, tenant_id)
                    if result is not None:
                        stats["processed"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as exc:
                    stats["failed"] += 1
                    await self.schedule_retry(row, str(exc), tenant_id)
                    logger.error(
                        "processing_row_error",
                        tenant_id=str(tenant_id),
                        outbox_id=str(row.id),
                        error=str(exc)[:200],
                        exc_info=True,
                    )

            await self._session.commit()

        return stats
