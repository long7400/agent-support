"""Telegram webhook API route.

POST /v1/webhook/telegram/{tenant_id}
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request

from app.infra.config import settings
from app.infra.database import AsyncSessionLocal
from app.infra.limiter import limiter
from app.infra.logging import bind_context, logger
from app.infra.tenant_context import with_tenant_context
from app.schemas.adapter import Platform
from app.services.platform_ingest import (
    DisabledChannelError,
    DuplicateAcceptedError,
    PlatformIngestService,
    SecretMismatchError,
    UnknownChannelError,
    UnknownPlatformMappingError,
)
from app.services.p2_audit import emit_audit_event, WEBHOOK_ACTOR
from app.services.telegram_adapter import normalize_telegram_update

router = APIRouter()


@router.post("/webhook/telegram/{tenant_id}")
@limiter.limit(settings.RATE_LIMIT_DEFAULT[0])
async def telegram_webhook(
    request: Request,
    tenant_id: UUID,
    body: dict[str, Any],
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, str]:
    """Accept a Telegram webhook update.

    - Verifies X-Telegram-Bot-Api-Secret-Token against stored hash
    - Normalizes the update into a NormalizedInboundEvent (NO tenant_id)
    - Resolves channel mapping from trusted DB state
    - Persists chat_event + processing_outbox atomically
    - Returns 200 for accepted new event and accepted duplicate
    - Returns 401 for secret mismatch
    - Fails closed on unknown/disabled mapping
    """
    bind_context(tenant_id=str(tenant_id), platform="telegram")

    # Reject missing secret token
    if not x_telegram_bot_api_secret_token:
        logger.warning("telegram_webhook_missing_secret", tenant_id=str(tenant_id))
        raise HTTPException(status_code=401, detail="Missing secret token")

    try:
        async with AsyncSessionLocal() as session:
            async with with_tenant_context(session, tenant_id):
                service = PlatformIngestService(session)

                # Verify webhook secret (resolves TenantPlatform)
                try:
                    tenant_platform = await service.verify_webhook_secret(
                        tenant_id=tenant_id,
                        platform=Platform.TELEGRAM,
                        secret_token=x_telegram_bot_api_secret_token,
                    )
                except SecretMismatchError:
                    logger.warning("telegram_webhook_secret_rejected", tenant_id=str(tenant_id))
                    await emit_audit_event(
                        session,
                        tenant_id=tenant_id,
                        actor=WEBHOOK_ACTOR,
                        action="webhook_secret_rejected",
                        metadata={"platform": "telegram"},
                    )
                    raise HTTPException(status_code=401, detail="Invalid secret token")
                except UnknownPlatformMappingError:
                    logger.warning("telegram_webhook_unknown_platform", tenant_id=str(tenant_id))
                    await emit_audit_event(
                        session,
                        tenant_id=tenant_id,
                        actor=WEBHOOK_ACTOR,
                        action="unknown_platform_mapping",
                        metadata={"platform": "telegram"},
                    )
                    raise HTTPException(status_code=404, detail="Platform not configured")

                # Normalize update
                try:
                    event = normalize_telegram_update(
                        body,
                        external_workspace_id=tenant_platform.external_workspace_id,
                    )
                except ValueError as exc:
                    logger.warning(
                        "telegram_webhook_normalization_failed",
                        tenant_id=str(tenant_id),
                        error=str(exc),
                    )
                    # Return 200 to Telegram to avoid retries on bad updates
                    return {"status": "ignored", "reason": "normalization_failed"}

                # Resolve channel
                try:
                    channel = await service.resolve_channel(
                        tenant_platform_id=tenant_platform.id,
                        external_channel_id=event.external_channel_id,
                        external_thread_id=event.external_thread_id,
                    )
                except UnknownChannelError:
                    logger.warning(
                        "telegram_webhook_unknown_channel",
                        tenant_id=str(tenant_id),
                        external_channel_id=event.external_channel_id,
                    )
                    await emit_audit_event(
                        session,
                        tenant_id=tenant_id,
                        actor=WEBHOOK_ACTOR,
                        action="unknown_channel_rejected",
                        metadata={
                            "platform": "telegram",
                            "external_channel_id": event.external_channel_id,
                        },
                    )
                    # Fail closed — drop update but return 200 to Telegram
                    return {"status": "ignored", "reason": "unknown_channel"}
                except DisabledChannelError:
                    logger.warning(
                        "telegram_webhook_disabled_channel",
                        tenant_id=str(tenant_id),
                        external_channel_id=event.external_channel_id,
                    )
                    await emit_audit_event(
                        session,
                        tenant_id=tenant_id,
                        actor=WEBHOOK_ACTOR,
                        action="disabled_channel_rejected",
                        metadata={
                            "platform": "telegram",
                            "external_channel_id": event.external_channel_id,
                        },
                    )
                    return {"status": "ignored", "reason": "disabled_channel"}

                # Persist event + outbox
                result = await service.ingest_event(
                    tenant_id=tenant_id,
                    event=event,
                    channel=channel,
                )

                if isinstance(result, DuplicateAcceptedError):
                    logger.info(
                        "telegram_webhook_duplicate_accepted",
                        tenant_id=str(tenant_id),
                        existing_event_id=str(result.existing_event_id),
                    )
                    await emit_audit_event(
                        session,
                        tenant_id=tenant_id,
                        actor=WEBHOOK_ACTOR,
                        action="duplicate_accepted",
                        metadata={
                            "platform": "telegram",
                            "existing_event_id": str(result.existing_event_id),
                        },
                    )
                    return {"status": "accepted", "duplicate": "true"}

                chat_event, _processing = result
                logger.info(
                    "telegram_webhook_event_accepted",
                    tenant_id=str(tenant_id),
                    event_id=str(chat_event.id),
                    message_type=event.message_type.value,
                )
                return {"status": "accepted"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("telegram_webhook_unhandled_error", tenant_id=str(tenant_id))
        raise HTTPException(status_code=500, detail="Internal server error")
