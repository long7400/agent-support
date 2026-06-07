"""Chatbot API endpoints using the harness runtime.

Phase 3: uses HarnessRunner with FakeModel (no real LLM calls).
Keeps the same API shape as the template chatbot but delegates to the
deterministic harness runtime.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from app.api.v1.auth import get_current_session
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.session import Session
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    Message,
)

# Phase 3: harness runtime replaces LangGraphAgent
from app.agent_harness.runner import HarnessRunner
from app.agent_harness.contracts import (
    TenantHarnessProfile,
    TrustedRuntimeEvent,
)

router = APIRouter()

# Module-level harness runner (stateless, no real LLM)
_runner = HarnessRunner()


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Process a chat request using the harness runtime.

    Uses FakeModel for deterministic responses — no real LLM calls.

    Args:
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing messages.
        session: The current session from the auth token.

    Returns:
        ChatResponse: The processed chat response.

    Raises:
        HTTPException: If there's an error processing the request.
    """
    try:
        logger.info(
            "harness_chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        # Get the last user message
        last_user_msg = None
        for msg in reversed(chat_request.messages):
            if msg.role == "user":
                last_user_msg = msg
                break

        if last_user_msg is None:
            return ChatResponse(messages=[Message(role="assistant", content="Please provide a message.")])

        # Build a trusted runtime event and run through harness
        event: TrustedRuntimeEvent = {
            "event_id": session.id.hex if hasattr(session.id, "hex") else session.id,
            "tenant_id": None,  # No tenant context for chatbot sessions
            "chat_event_id": session.id.hex if hasattr(session.id, "hex") else session.id,
            "platform": "telegram",
            "channel_id": None,
            "thread_id": None,
            "user_id_hash": str(session.user_id or ""),
            "message_type": "text",
            "text_preview": last_user_msg.content,
            "metadata": {},
        }

        # Phase 3: inline harness run without DB session
        from app.agent_harness.middleware.stack import build_default_middleware_stack
        from app.agent_harness.models.fake_model import FakeModel
        from app.agent_harness.capabilities.registry import FakeCapabilityRegistry
        from app.agent_harness.runtime import AgentHarnessRuntime

        model = FakeModel()
        registry = FakeCapabilityRegistry()
        middleware = build_default_middleware_stack()
        runtime = AgentHarnessRuntime(model, registry, middleware)

        profile: TenantHarnessProfile = {
            "tenant_id": None,
            "config_version": 1,
            "policy_version": 1,
            "enabled_platforms": ["telegram", "discord"],
            "allowed_capabilities": ["fake_search", "official_links"],
            "model_policy": {},
            "memory_policy": {},
            "moderation_policy": {"mode": "shadow"},
            "escalation_policy": {},
            "budgets": {},
        }

        result = await runtime.run(event, profile)
        response_text = result.get("response_text", "I'm a fake model response.")

        logger.info(
            "harness_chat_request_processed",
            session_id=session.id,
            status=result.get("status"),
        )

        return ChatResponse(messages=[Message(role="assistant", content=response_text)])
    except Exception as e:
        logger.exception("harness_chat_request_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def get_session_messages(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Get all messages for a session.

    Phase 3: returns empty history since harness doesn't track chatbot sessions.
    """
    return ChatResponse(messages=[])


@router.delete("/messages")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def clear_chat_history(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Clear all messages for a session.

    Phase 3: no-op since messages are not persisted for chatbot sessions.
    """
    return {"message": "Chat history cleared successfully"}
