"""Long-term memory service using mem0 and pgvector with optional cache layer."""

import inspect
from typing import Any, cast

from mem0 import AsyncMemory

from app.infra.cache import (
    cache_key,
    cache_service,
)
from app.infra.config import settings
from app.infra.logging import logger
from app.models.long_term_memory import MemoryRetrievalPolicy, memory_result_allowed, memory_result_text


class MemoryService:
    """Service for managing long-term memory using mem0 and pgvector."""

    def __init__(self):
        """Initialize the memory service."""
        self._memory: AsyncMemory | None = None

    async def _get_memory(self) -> AsyncMemory:
        if not settings.LONG_TERM_MEMORY_ENABLED:
            raise RuntimeError("long term memory is disabled")
        if self._memory is None:
            memory_result: Any = AsyncMemory.from_config(
                config_dict={
                    "vector_store": {
                        "provider": "pgvector",
                        "config": {
                            "collection_name": settings.LONG_TERM_MEMORY_COLLECTION_NAME,
                            "dbname": settings.POSTGRES_DB,
                            "user": settings.POSTGRES_USER,
                            "password": settings.POSTGRES_PASSWORD,
                            "host": settings.POSTGRES_HOST,
                            "port": settings.POSTGRES_PORT,
                        },
                    },
                    "llm": {
                        "provider": "openai",
                        "config": {"model": settings.LONG_TERM_MEMORY_MODEL},
                    },
                    "embedder": {
                        "provider": "openai",
                        "config": {"model": settings.LONG_TERM_MEMORY_EMBEDDER_MODEL},
                    },
                }
            )
            if inspect.isawaitable(memory_result):
                memory_result = await memory_result
            self._memory = cast(AsyncMemory, memory_result)
        return self._memory

    async def initialize(self) -> None:
        """Pre-warm the mem0 AsyncMemory instance and its pgvector connection pool.

        Call once at startup so the first search() or add() doesn't pay the
        ~130ms from_config + pgvector.list_cols() cold-init cost.
        """
        if not settings.LONG_TERM_MEMORY_ENABLED:
            logger.info("memory_service_disabled")
            return
        await self._get_memory()
        logger.info("memory_service_initialized")

    async def search(
        self,
        user_id: str | None,
        query: str,
        *,
        tenant_id: str | None = None,
        scope: str | None = None,
        visibility: list[str] | tuple[str, ...] | None = None,
    ) -> str:
        """Search relevant memories only after tenant policy can be enforced."""
        policy = MemoryRetrievalPolicy.from_context(
            tenant_id=tenant_id,
            user_id=user_id,
            scope=scope,
            visibility=visibility,
        )
        if policy is None or not settings.LONG_TERM_MEMORY_ENABLED:
            return ""
        try:
            key = cache_key("memory", policy.tenant_id, policy.user_id, policy.scope, ",".join(policy.visibility), query)
            cached = await cache_service.get(key)
            if cached is not None:
                logger.debug("memory_search_cache_hit", user_id=policy.user_id, tenant_id=policy.tenant_id)
                return cached

            memory = await self._get_memory()
            results = await memory.search(user_id=policy.user_id, query=query)
            raw_results = results.get("results", []) if isinstance(results, dict) else []
            filtered = [r for r in raw_results if isinstance(r, dict) and memory_result_allowed(r, policy)]
            result = "\n".join([f"* {memory_result_text(r)}" for r in filtered if memory_result_text(r)])

            if result:
                await cache_service.set(key, result)

            return result
        except Exception as e:
            logger.error("failed_to_get_relevant_memory", error=str(e), user_id=user_id, tenant_id=tenant_id, query=query)
            return ""

    async def add(self, user_id: str | None, messages: list[dict], metadata: dict | None = None) -> None:
        """Add messages to long-term memory for a user.

        No-op when ``user_id`` is ``None`` (see ``search`` for rationale).
        """
        if user_id is None or not settings.LONG_TERM_MEMORY_ENABLED or not settings.LONG_TERM_MEMORY_WRITE_ENABLED:
            return
        try:
            memory = await self._get_memory()
            await memory.add(messages, user_id=str(user_id), metadata=metadata)
            logger.info("long_term_memory_updated_successfully", user_id=user_id)
        except Exception as e:
            logger.exception("failed_to_update_long_term_memory", user_id=user_id, error=str(e))


memory_service = MemoryService()
