"""Observability module for the application."""

from typing import Optional

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from app.core.config import (
    Environment,
    settings,
)
from app.core.logging import logger


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
