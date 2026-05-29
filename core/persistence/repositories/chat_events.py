from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.api.schemas.messages import MessageDirection, Platform
from core.persistence.models import ChatEvent


class ChatEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def insert_inbound_idempotent(
        self,
        *,
        tenant_id: UUID,
        trace_id: UUID,
        platform: Platform,
        channel_id: str,
        user_id: str,
        message_id: str,
        text: str,
        thread_id: str | None,
    ) -> tuple[bool, ChatEvent]:
        statement = (
            pg_insert(ChatEvent)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                trace_id=trace_id,
                platform=platform.value,
                direction=MessageDirection.INBOUND.value,
                channel_id=channel_id,
                user_id=user_id,
                message_id=message_id,
                thread_id=thread_id,
                text=text,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    ChatEvent.tenant_id,
                    ChatEvent.platform,
                    ChatEvent.channel_id,
                    ChatEvent.message_id,
                    ChatEvent.direction,
                ],
            )
            .returning(ChatEvent.id)
        )
        inserted_id = self.session.execute(statement).scalar_one_or_none()
        if inserted_id is not None:
            chat_event = self.session.get(ChatEvent, inserted_id)
            if chat_event is None:
                raise RuntimeError("chat event insert did not return a persisted row")
            self.session.refresh(chat_event)
            return True, chat_event

        existing = self._get_existing_inbound(
            tenant_id=tenant_id,
            platform=platform,
            channel_id=channel_id,
            message_id=message_id,
        )
        if existing is None:
            raise RuntimeError("chat event conflict did not resolve to an existing row")
        return False, existing

    def _get_existing_inbound(
        self,
        *,
        tenant_id: UUID,
        platform: Platform,
        channel_id: str,
        message_id: str,
    ) -> ChatEvent | None:
        statement = select(ChatEvent).where(
            ChatEvent.tenant_id == tenant_id,
            ChatEvent.platform == platform.value,
            ChatEvent.channel_id == channel_id,
            ChatEvent.message_id == message_id,
            ChatEvent.direction == MessageDirection.INBOUND.value,
        )
        return self.session.scalars(statement).one_or_none()
