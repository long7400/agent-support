from uuid import uuid4

from core.api.schemas.messages import MessageDirection, Platform, StreamMessageEnvelope
from core.workers.message_stub import _outbound_stub


def test_outbound_stub_keeps_text_preview_within_stream_contract() -> None:
    inbound = StreamMessageEnvelope(
        trace_id=uuid4(),
        tenant_id=uuid4(),
        chat_event_id=uuid4(),
        direction=MessageDirection.INBOUND,
        platform=Platform.TELEGRAM,
        channel_id="channel-a",
        user_id="user-a",
        message_id="message-a",
        text_preview="x" * 500,
    )

    outbound = _outbound_stub(inbound)

    assert outbound.direction == MessageDirection.OUTBOUND
    assert outbound.reply_to_message_id == inbound.message_id
    assert outbound.inbound_chat_event_id == inbound.chat_event_id
    assert len(outbound.text) == 500
    assert outbound.text.startswith("stub:")
