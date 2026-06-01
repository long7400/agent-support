"""Runtime preflight checks for production-safe infrastructure defaults."""

from app.core.config import (
    Environment,
    settings,
)
from app.core.kms import validate_kms_configuration
from app.core.logging import logger


class RuntimeGuardrailError(RuntimeError):
    """Raised when runtime configuration violates a fail-closed guardrail."""


def validate_runtime_guardrails() -> None:
    """Validate runtime settings before external services are initialized."""
    validate_kms_configuration()

    insecure_defaults = settings.insecure_defaults()
    if settings.ENVIRONMENT != Environment.PRODUCTION:
        logger.info(
            "runtime_guardrails_checked",
            environment=settings.ENVIRONMENT.value,
            web_search_enabled=settings.WEB_SEARCH_ENABLED,
            long_term_memory_enabled=settings.LONG_TERM_MEMORY_ENABLED,
            kms_provider=settings.KMS_PROVIDER,
        )
        return

    failed = [name for name, is_failed in insecure_defaults.items() if is_failed]
    if failed:
        logger.error("production_guardrail_failed", failed_checks=failed)
        raise RuntimeGuardrailError("production runtime guardrails failed")

    logger.info("production_guardrails_passed")
