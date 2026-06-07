"""Observability module for the application."""

from copy import deepcopy
from typing import Any, Optional

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from app.infra.config import (
    Environment,
    settings,
)
from app.infra.logging import logger

_RAG_OBSERVABILITY_EVENTS: list[dict[str, Any]] = []
_RAG_METADATA_KEYS = {
    "active_only",
    "candidate_count",
    "candidate_top_k",
    "chunks_embedded",
    "documents_processed",
    "event",
    "final_top_k",
    "job_id",
    "lexical_indexed",
    "refusal_reason",
    "returned_count",
    "retrieval_mode",
    "source_id",
    "source_ids",
    "source_version_id",
    "source_version_ids",
    "status",
    "tenant_id",
    "vectors_upserted",
}


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in _RAG_METADATA_KEYS:
            safe[key] = value
    return safe


def record_rag_observability_event(name: str, **metadata: Any) -> None:
    """Record deterministic RAG metadata without source/query text."""
    safe = _safe_metadata(metadata)
    _RAG_OBSERVABILITY_EVENTS.append({"name": name, "metadata": deepcopy(safe)})
    logger.info(name.replace(".", "_"), **safe)


def get_rag_observability_events() -> list[dict[str, Any]]:
    """Return a copy of captured RAG observability events for tests."""
    return deepcopy(_RAG_OBSERVABILITY_EVENTS)


def clear_rag_observability_events() -> None:
    """Clear captured RAG observability events."""
    _RAG_OBSERVABILITY_EVENTS.clear()


def langfuse_init() -> None:
    """Initialize Langfuse."""
    if not settings.LANGFUSE_TRACING_ENABLED:
        logger.info("langfuse_tracing_disabled")
        return

    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        logger.warning("langfuse_credentials_missing")
        return

    langfuse = Langfuse(
        tracing_enabled=settings.LANGFUSE_TRACING_ENABLED,
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_HOST,
        environment=settings.ENVIRONMENT.value,
        debug=settings.DEBUG,
    )

    try:
        if langfuse.auth_check():
            logger.debug("langfuse_auth_success")
        else:
            logger.warning("langfuse_auth_failure")
    except Exception as exc:
        logger.exception("langfuse_auth_check_failed", error=str(exc), host=settings.LANGFUSE_HOST)
        if settings.ENVIRONMENT == Environment.PRODUCTION:
            raise


def get_langfuse_callback_handler() -> Optional[CallbackHandler]:
    """Create a Langfuse CallbackHandler for tracking LLM interactions.

    Returns:
        CallbackHandler: Configured Langfuse callback handler when tracing is enabled.
    """
    if not settings.LANGFUSE_TRACING_ENABLED:
        return None
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        return None
    return CallbackHandler()


langfuse_callback_handler: Optional[CallbackHandler] = get_langfuse_callback_handler()
