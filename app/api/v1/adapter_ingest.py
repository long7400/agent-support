"""Generic adapter ingest API route.

POST /v1/adapter/ingest
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.limiter import limiter
from app.core.logging import bind_context, logger
from app.core.tenant_context import with_tenant_context
from app.schemas.adapter import AdapterPrincipal, NormalizedInboundEvent, Platform
from app.services.platform_ingest import (
    DisabledChannelError,
    DuplicateAcceptedError,
    InvalidAdapterCredentialError,
    PlatformIngestService,
    UnknownChannelError,
    resolve_adapter_credential,
)
from app.services.p2_audit import emit_audit_event, ADAPTER_ACTOR

router = APIRouter()


async def require_adapter_principal(
    x_adapter_credential: Annotated[str | None, Header()] = None,
) -> AdapterPrincipal:
    """Authenticate an adapter principal from the X-Adapter-Credential header.

    This is a separate auth path from human JWT or service-principal auth.
    """
    if not x_adapter_credential:
        raise HTTPException(status_code=401, detail="Missing adapter credential")

    async with AsyncSessionLocal() as session:
        try:
            credential = await resolve_adapter_credential(
                session,
                credential_raw=x_adapter_credential,
            )
        except InvalidAdapterCredentialError as exc:
            logger.warning(
                "adapter_ingest_invalid_credential",
                reason=exc.reason,
            )
            raise HTTPException(status_code=401, detail="Invalid adapter credential")

        return AdapterPrincipal(
            adapter_credential_id=credential.id,
            platform=Platform(credential.platform),
            name=credential.name,
            credential_prefix=credential.credential_prefix,
            allowed_channel_patterns=tuple(credential.allowed_channel_patterns),
            scopes=tuple(credential.scopes),
            tenant_id=credential.tenant_id,
            status=credential.status,
        )


@router.post("/adapter/ingest")
@limiter.limit(settings.RATE_LIMIT_DEFAULT[0])
async def adapter_ingest(
    request: Request,
    body: NormalizedInboundEvent,
    principal: AdapterPrincipal = Depends(require_adapter_principal),
) -> dict[str, str]:
    """Accept a normalized inbound event from an adapter principal.

    - Authenticates via X-Adapter-Credential header
    - Validates NormalizedInboundEvent (tenant_id is FORBIDDEN in body)
    - Checks principal scope covers the requested channel/platform
    - Resolves channel mapping from trusted DB state
    - Persists chat_event + processing_outbox atomically
    - Returns 200 for accepted new event and accepted duplicate
    """
    # Validate principal is active
    if not principal.is_active():
        logger.warning(
            "adapter_ingest_inactive_credential",
            tenant_id=str(principal.tenant_id) if principal.tenant_id else None,
        )
        raise HTTPException(status_code=403, detail="Adapter credential is not active")

    # Validate principal tenant_id is set (from trusted lookup)
    if principal.tenant_id is None:
        logger.warning("adapter_ingest_no_tenant_binding")
        raise HTTPException(status_code=403, detail="Adapter credential has no tenant binding")

    tenant_id = principal.tenant_id
    bind_context(tenant_id=str(tenant_id), platform=body.platform.value, adapter=principal.name)

    # Validate platform matches
    if body.platform != principal.platform:
        logger.warning(
            "adapter_ingest_platform_mismatch",
            tenant_id=str(tenant_id),
            body_platform=body.platform.value,
            principal_platform=principal.platform.value,
        )
        raise HTTPException(status_code=403, detail="Platform scope mismatch")

    # Validate channel scope
    if not principal.is_channel_allowed(body.external_channel_id):
        logger.warning(
            "adapter_ingest_channel_not_allowed",
            tenant_id=str(tenant_id),
            external_channel_id=body.external_channel_id,
        )
        async with AsyncSessionLocal() as session:
            async with with_tenant_context(session, tenant_id):
                await emit_audit_event(
                    session,
                    tenant_id=tenant_id,
                    actor=ADAPTER_ACTOR,
                    action="scope_mismatch_rejected",
                    metadata={
                        "platform": body.platform.value,
                        "external_channel_id": body.external_channel_id,
                        "reason": "channel_not_allowed",
                    },
                )
                await session.commit()
        raise HTTPException(status_code=403, detail="Channel not allowed by adapter scope")

    try:
        async with AsyncSessionLocal() as session:
            async with with_tenant_context(session, tenant_id):
                service = PlatformIngestService(session)

                # Resolve platform from principal
                try:
                    from sqlalchemy import select
                    from app.models.platform import TenantPlatform

                    result = await session.execute(
                        select(TenantPlatform).where(
                            TenantPlatform.tenant_id == tenant_id,
                            TenantPlatform.platform == principal.platform.value,
                            TenantPlatform.status == "active",
                        )
                    )
                    tenant_platform = result.scalar_one_or_none()
                    if tenant_platform is None:
                        raise HTTPException(status_code=404, detail="Platform not configured")
                except HTTPException:
                    raise

                # Resolve channel
                try:
                    channel = await service.resolve_channel(
                        tenant_platform_id=tenant_platform.id,
                        external_channel_id=body.external_channel_id,
                        external_thread_id=body.external_thread_id,
                    )
                except UnknownChannelError:
                    logger.warning(
                        "adapter_ingest_unknown_channel",
                        tenant_id=str(tenant_id),
                        external_channel_id=body.external_channel_id,
                    )
                    await emit_audit_event(
                        session,
                        tenant_id=tenant_id,
                        actor=ADAPTER_ACTOR,
                        action="unknown_channel_rejected",
                        metadata={
                            "platform": body.platform.value,
                            "external_channel_id": body.external_channel_id,
                        },
                    )
                    raise HTTPException(status_code=404, detail="Unknown channel")
                except DisabledChannelError:
                    logger.warning(
                        "adapter_ingest_disabled_channel",
                        tenant_id=str(tenant_id),
                        external_channel_id=body.external_channel_id,
                    )
                    await emit_audit_event(
                        session,
                        tenant_id=tenant_id,
                        actor=ADAPTER_ACTOR,
                        action="disabled_channel_rejected",
                        metadata={
                            "platform": body.platform.value,
                            "external_channel_id": body.external_channel_id,
                        },
                    )
                    raise HTTPException(status_code=403, detail="Channel is disabled")

                # Persist event + outbox
                result = await service.ingest_event(
                    tenant_id=tenant_id,
                    event=body,
                    channel=channel,
                )

                if isinstance(result, DuplicateAcceptedError):
                    logger.info(
                        "adapter_ingest_duplicate_accepted",
                        tenant_id=str(tenant_id),
                        existing_event_id=str(result.existing_event_id),
                    )
                    await emit_audit_event(
                        session,
                        tenant_id=tenant_id,
                        actor=ADAPTER_ACTOR,
                        action="duplicate_accepted",
                        metadata={
                            "platform": body.platform.value,
                            "existing_event_id": str(result.existing_event_id),
                        },
                    )
                    return {"status": "accepted", "duplicate": "true"}

                chat_event, _processing = result
                logger.info(
                    "adapter_ingest_event_accepted",
                    tenant_id=str(tenant_id),
                    event_id=str(chat_event.id),
                    message_type=body.message_type.value,
                )
                return {"status": "accepted"}

    except HTTPException:
        raise
    except Exception:
        logger.exception("adapter_ingest_unhandled_error", tenant_id=str(tenant_id))
        raise HTTPException(status_code=500, detail="Internal server error")
