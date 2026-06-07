"""LLM service stub.

Phase 3: no real LLM calls.  This file exists for import compatibility.
Use app/agent_harness/models/fake_model.py instead.
"""

from __future__ import annotations


from app.services.llm import LLMService


class LLMServiceStub(LLMService):
    """Stub that raises on call."""


llm_service = LLMService()
