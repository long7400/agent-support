"""Worker process with SKIP LOCKED outbox claiming.

Phase 2 implements two worker roles:
- processing: claims processing_outbox rows and creates delivery_outbox entries
- delivery: claims delivery_outbox rows and sends via platform adapters

Both roles use FOR UPDATE SKIP LOCKED for safe concurrent claiming.
A single worker process can run both roles if WORKER_ROLE=processing,delivery.
"""

import asyncio
import signal

from app.core.cache import cache_service
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.core.runtime_guardrails import validate_runtime_guardrails
from app.services.outbox_worker import ProcessingOutboxWorker
from app.services.delivery_sender import DeliverySender
from app.services.rate_limits import RateLimiter


class WorkerService:
    """Long-running worker process with outbox claiming."""

    def __init__(self) -> None:
        """Initialize worker state."""
        self._stop_event = asyncio.Event()
        self._rate_limiter = RateLimiter()
        self._roles = self._parse_roles(settings.WORKER_ROLE)

    def _parse_roles(self, role_str: str) -> set[str]:
        """Parse WORKER_ROLE config into a set of role names."""
        roles = {r.strip().lower() for r in role_str.split(",")}
        # Normalize: "runtime" is the legacy Phase 0 role, treat as "processing"
        if "runtime" in roles:
            roles.discard("runtime")
            roles.add("processing")
        return roles

    def request_stop(self) -> None:
        """Request a graceful worker shutdown."""
        self._stop_event.set()

    async def run(self) -> None:
        """Run the worker until a shutdown signal is received."""
        validate_runtime_guardrails()
        await cache_service.initialize()
        logger.info(
            "worker_started",
            roles=list(self._roles),
            poll_interval_seconds=settings.WORKER_POLL_INTERVAL_SECONDS,
        )
        try:
            while not self._stop_event.is_set():
                await self._tick()
                # Sleep until next tick or stop signal
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=settings.WORKER_POLL_INTERVAL_SECONDS,
                    )
                except TimeoutError:
                    continue
        finally:
            await cache_service.close()
            logger.info("worker_stopped", roles=list(self._roles))

    async def _tick(self) -> None:
        """Execute one worker tick across all configured roles."""
        if "processing" in self._roles:
            await self._run_processing_cycle()
        if "delivery" in self._roles:
            await self._run_delivery_cycle()

    async def _run_processing_cycle(self) -> None:
        """Run one processing outbox cycle."""
        try:
            async with AsyncSessionLocal() as session:
                worker = ProcessingOutboxWorker(session)
                # Get tenants with pending work (cross-tenant scan)
                tenant_ids = await worker.get_tenants_with_pending_processing()
                await session.rollback()  # End discovery transaction before tenant-scoped cycles.
                logger.debug("processing_tenants_found", count=len(tenant_ids))
                for tenant_id in tenant_ids:
                    await worker.run_cycle(tenant_id)
                    if self._stop_event.is_set():
                        break
        except Exception as exc:
            logger.error("processing_cycle_error", error=str(exc), exc_info=True)

    async def _run_delivery_cycle(self) -> None:
        """Run one delivery outbox cycle."""
        try:
            async with AsyncSessionLocal() as session:
                sender = DeliverySender(session, rate_limiter=self._rate_limiter)
                # Get tenants with pending deliveries (cross-tenant scan)
                tenant_ids = await sender.get_tenants_with_pending_delivery()
                await session.rollback()  # End discovery transaction before tenant-scoped cycles.
                logger.debug("delivery_tenants_found", count=len(tenant_ids))
                for tenant_id in tenant_ids:
                    await sender.run_cycle(tenant_id)
                    if self._stop_event.is_set():
                        break
        except Exception as exc:
            logger.error("delivery_cycle_error", error=str(exc), exc_info=True)


def _install_signal_handlers(worker: WorkerService) -> None:
    """Register SIGINT/SIGTERM handlers for graceful shutdown."""
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, worker.request_stop)


async def _main() -> None:
    """Run the worker process."""
    worker = WorkerService()
    _install_signal_handlers(worker)
    await worker.run()


def main() -> None:
    """Run the worker process entrypoint."""
    asyncio.run(_main())


if __name__ == "__main__":
    main()
