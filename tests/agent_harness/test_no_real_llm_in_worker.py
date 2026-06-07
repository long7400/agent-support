"""Source guardrail tests — verify real LLM imports are not used in worker/harness code.

Phase 3 must not use real LLM calls in the default worker or harness path.
All model calls go through FakeModel only.
"""

from pathlib import Path


def test_outbox_worker_does_not_import_real_llm() -> None:
    """outbox_worker.py must not import app.services.llm (real LLM)."""
    source = Path("app/services/outbox_worker.py").read_text()
    assert "app.services.llm" not in source, "Worker must not import real LLM service"


def test_harness_runner_does_not_import_real_llm() -> None:
    """runner.py must not import app.services.llm (real LLM)."""
    source = Path("app/agent_harness/runner.py").read_text()
    assert "app.services.llm" not in source, "Runner must not import real LLM service"


def test_harness_runtime_does_not_import_real_llm() -> None:
    """runtime.py must not import real LLM or LangChain chat models."""
    source = Path("app/agent_harness/runtime.py").read_text()
    assert "ChatOpenAI" not in source, "Runtime must not import ChatOpenAI"
    assert "langchain_openai" not in source, "Runtime must not import langchain_openai"
    assert "app.services.llm" not in source, "Runtime must not import app.services.llm"


def test_fake_model_is_default_in_runner() -> None:
    """Runner must use FakeModel as the default model."""
    source = Path("app/agent_harness/runner.py").read_text()
    assert "FakeModel" in source, "Runner must reference FakeModel"
    assert "FakeModel()" in source, "Runner must default to FakeModel"


def test_no_chat_openai_in_harness_package() -> None:
    """No file in app/agent_harness/ should import ChatOpenAI."""
    for pyfile in Path("app/agent_harness").rglob("*.py"):
        source = pyfile.read_text()
        if "ChatOpenAI" in source:
            raise AssertionError(f"{pyfile} imports ChatOpenAI")
        if "langchain_openai" in source:
            raise AssertionError(f"{pyfile} imports langchain_openai")
