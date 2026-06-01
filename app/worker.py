"""Phase-0 worker process skeleton.

The worker container exists before Phase 2 outbox processing is implemented so
the deployment topology is stable early. Phase 2 replaces the idle loop with
SKIP LOCKED outbox claiming and graph execution.
"""

import asyncio
import signal

from app.core.cache import cache_service
from app.core.config import settings
from app.core.logging import logger
from app.core.runtime_guardrails import validate_runtime_guardrails


class WorkerService:
    """Long-running worker process placeholder."""

    def __init__(self) -> None:
        """Initialize worker state."""
        self._stop_event = asyncio.Event()

    def request_stop(self) -> None:
        """Request a graceful worker shutdown."""
        self._stop_event.set()

    async def run(self) -> None:
        """Run the worker until a shutdown signal is received."""
        validate_runtime_guardrails()
        await cache_service.initialize()
        logger.info(
            "worker_started",
            role=settings.WORKER_ROLE,
            poll_interval_seconds=settings.WORKER_POLL_INTERVAL_SECONDS,
        )
        try:
            while not self._stop_event.is_set():
                logger.debug("worker_idle_tick", role=settings.WORKER_ROLE)
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=settings.WORKER_POLL_INTERVAL_SECONDS,
                    )
                except TimeoutError:
                    continue
        finally:
            await cache_service.close()
            logger.info("worker_stopped", role=settings.WORKER_ROLE)


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
