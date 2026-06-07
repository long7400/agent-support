# pyright: reportArgumentType=false, reportIndexIssue=false, reportTypedDictNotRequiredAccess=false
# ruff: noqa: D101,D102,D103,D107
"""Tests for prompt-visible RAG evidence formatting."""

from uuid import uuid4

import pytest


from app.agent_harness.middleware.dynamic_prompt import DynamicPromptMiddleware


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_dynamic_prompt_formats_retrieved_snippets_as_delimited_evidence():
    source_id = uuid4()
    version_id = uuid4()
    chunk_id = uuid4()
    state = {
        "messages": [{"role": "user", "content": "What is the SLA?"}],
        "retrieved_evidence": [
            {
                "chunk_id": str(chunk_id),
                "text": "SLA is 24 hours.",
                "citation": {
                    "source_id": str(source_id),
                    "source_version_id": str(version_id),
                    "chunk_id": str(chunk_id),
                },
            }
        ],
    }

    out = await DynamicPromptMiddleware().before_model(state, {})

    system = out["messages"][0]["content"]
    assert "BEGIN RETRIEVED EVIDENCE" in system
    assert "END RETRIEVED EVIDENCE" in system
    assert "Evidence item 1" in system
    assert f"source_id={source_id}" in system
    assert f"source_version_id={version_id}" in system
    assert f"chunk_id={chunk_id}" in system
    assert "SLA is 24 hours." in system


@pytest.mark.anyio
async def test_dynamic_prompt_limits_visible_evidence_count_and_size():
    snippets = [{"chunk_id": str(uuid4()), "text": "x" * 2000, "citation": {}} for _ in range(20)]
    state = {"messages": [], "retrieved_evidence": snippets}

    out = await DynamicPromptMiddleware().before_model(state, {})

    system = out["messages"][0]["content"]
    assert 1 <= system.count("Evidence item") <= 5
    assert system.count("x") <= 4001
