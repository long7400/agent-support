from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.persistence.models import StreamOutbox

OUTBOX_PENDING = "pending"
OUTBOX_FAILED = "failed"
OUTBOX_PUBLISHED = "published"

JsonObject = dict[str, object]


class StreamOutboxRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def enqueue_once(
        self,
        *,
        tenant_id: UUID,
        chat_event_id: UUID,
        stream_name: str,
        payload: JsonObject,
    ) -> StreamOutbox:
        statement = (
            pg_insert(StreamOutbox)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                chat_event_id=chat_event_id,
                stream_name=stream_name,
                payload=payload,
                status=OUTBOX_PENDING,
            )
            .on_conflict_do_nothing(
                index_elements=[StreamOutbox.chat_event_id, StreamOutbox.stream_name],
            )
            .returning(StreamOutbox.id)
        )
        outbox_id = self.session.execute(statement).scalar_one_or_none()
        if outbox_id is not None:
            row = self.session.get(StreamOutbox, outbox_id)
            if row is None:
                raise RuntimeError("stream outbox insert did not return a persisted row")
            self.session.refresh(row)
            return row

        row = self.get_for_chat_event(chat_event_id=chat_event_id, stream_name=stream_name)
        if row is None:
            raise RuntimeError("stream outbox conflict did not resolve to an existing row")
        return row

    def get_for_chat_event(
        self,
        *,
        chat_event_id: UUID,
        stream_name: str,
    ) -> StreamOutbox | None:
        statement = select(StreamOutbox).where(
            StreamOutbox.chat_event_id == chat_event_id,
            StreamOutbox.stream_name == stream_name,
        )
        return self.session.scalars(statement).one_or_none()

    def mark_published(self, *, outbox_id: UUID, redis_message_id: str) -> StreamOutbox:
        row = self._get_required(outbox_id)
        row.status = OUTBOX_PUBLISHED
        row.redis_message_id = redis_message_id
        row.last_error = None
        row.published_at = datetime.now(UTC)
        self.session.flush()
        self.session.refresh(row)
        return row

    def mark_failed(self, *, outbox_id: UUID, error: str) -> StreamOutbox:
        row = self._get_required(outbox_id)
        row.status = OUTBOX_PENDING
        row.attempts += 1
        row.last_error = error[:500]
        self.session.flush()
        self.session.refresh(row)
        return row

    def _get_required(self, outbox_id: UUID) -> StreamOutbox:
        row = self.session.get(StreamOutbox, outbox_id)
        if row is None:
            raise RuntimeError("stream outbox row not found")
        return row
