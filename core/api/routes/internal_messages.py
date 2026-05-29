from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from core.api.dependencies import get_admin_session, require_internal_token
from core.api.schemas.messages import (
    InboundMessageEnvelope,
    IngestAcceptedResponse,
    StreamMessageEnvelope,
)
from core.config import Settings, get_settings
from core.persistence.repositories.stream_outbox import (
    OUTBOX_PUBLISHED,
    StreamOutboxRepository,
)
from core.persistence.rls import tenant_session
from core.services.errors import ServiceError
from core.services.messages import TrustedMessageIngestService, tenant_id_from_platform_mapping
from core.services.platforms import TenantPlatformService
from core.streams.names import StreamDirection, stream_name
from core.streams.publisher import RedisStreamPublisher
from core.streams.redis_client import create_redis_client

router = APIRouter(prefix="/internal/messages", tags=["internal-messages"])

AdminSessionDep = Annotated[Session, Depends(get_admin_session)]
InternalTokenDep = Annotated[None, Depends(require_internal_token)]


class StreamPublisherProtocol(Protocol):
    def publish(
        self,
        *,
        stream: str,
        envelope: StreamMessageEnvelope,
        group: str | None = None,
    ) -> str: ...


def get_tenant_platform_service(
    token: InternalTokenDep,
    session: AdminSessionDep,
) -> TenantPlatformService:
    del token
    return TenantPlatformService.from_session(session)


def get_stream_publisher() -> StreamPublisherProtocol:
    settings = get_settings()
    return RedisStreamPublisher(redis=create_redis_client(settings), settings=settings)


TenantPlatformServiceDep = Annotated[TenantPlatformService, Depends(get_tenant_platform_service)]
StreamPublisherDep = Annotated[StreamPublisherProtocol, Depends(get_stream_publisher)]


@router.post("/ingest", response_model=IngestAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_message(
    http_request: Request,
    request: InboundMessageEnvelope,
    platform_service: TenantPlatformServiceDep,
    publisher: StreamPublisherDep,
) -> IngestAcceptedResponse:
    settings = get_settings()
    platform_mapping = platform_service.resolve_active(
        platform=request.platform,
        external_workspace_id=request.external_workspace_id,
        external_channel_id=request.channel_id,
    )
    tenant_id = tenant_id_from_platform_mapping(platform_mapping)
    with tenant_session(tenant_id) as session:
        result = TrustedMessageIngestService.from_session(session).ingest_inbound_message(
            request,
            tenant_id=tenant_id,
        )
        outbox = StreamOutboxRepository(session).enqueue_once(
            tenant_id=tenant_id,
            chat_event_id=result.chat_event_id,
            stream_name=_ingress_stream(result.stream_message, settings),
            payload=result.stream_message.model_dump(mode="json"),
        )
    http_request.state.trace_id = result.stream_message.trace_id
    if outbox.status != OUTBOX_PUBLISHED:
        try:
            redis_message_id = publisher.publish(
                stream=outbox.stream_name,
                envelope=StreamMessageEnvelope.model_validate(outbox.payload),
                group=settings.redis_ingress_consumer_group,
            )
        except ServiceError as exc:
            with tenant_session(tenant_id) as session:
                StreamOutboxRepository(session).mark_failed(
                    outbox_id=outbox.id,
                    error=str(exc),
                )
            raise
        with tenant_session(tenant_id) as session:
            StreamOutboxRepository(session).mark_published(
                outbox_id=outbox.id,
                redis_message_id=redis_message_id,
            )
    return IngestAcceptedResponse(
        trace_id=result.stream_message.trace_id,
        chat_event_id=result.chat_event_id,
    )


def _ingress_stream(envelope: StreamMessageEnvelope, settings: Settings) -> str:
    return stream_name(
        environment=settings.environment,
        tenant_scope=str(envelope.tenant_id),
        direction=StreamDirection.INGRESS,
        platform=envelope.platform,
    )
