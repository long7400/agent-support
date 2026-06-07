"""Long-term memory retrieval policy tests."""

from __future__ import annotations

import asyncio
from typing import Any, cast, override

import pytest

from app.infra.config import settings
from app.services.memory import AsyncMemory, MemoryService


class FakeMemoryBackend:
    """Minimal mem0-compatible fake for policy filtering."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        """Store fake search results."""
        self.results = results
        self.calls: list[dict[str, str]] = []

    async def search(self, *, user_id: str, query: str) -> dict[str, Any]:
        """Return fake mem0 search results."""
        self.calls.append({"user_id": user_id, "query": query})
        return {"results": self.results}


class FakeMemoryService(MemoryService):
    """Memory service wired to a fake backend."""

    def __init__(self, backend: FakeMemoryBackend) -> None:
        """Store fake backend dependency."""
        super().__init__()
        self.backend = backend

    @override
    async def _get_memory(self) -> AsyncMemory:
        """Return the fake backend instead of constructing mem0."""
        return cast(AsyncMemory, self.backend)


def run(coro: Any) -> Any:
    """Run an async service call in sync tests."""
    return asyncio.run(coro)


def test_memory_retrieval_disabled_denies_without_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabled memory retrieval fails closed before backend access."""
    monkeypatch.setattr(settings, "LONG_TERM_MEMORY_ENABLED", False)
    backend = FakeMemoryBackend([
        {"memory": "should not leak", "metadata": {"tenant_id": "t1", "user_id": "u1", "scope": "support", "visibility": "private", "active": True}}
    ])
    service = FakeMemoryService(backend)

    result = run(service.search("u1", "hello", tenant_id="t1", scope="support", visibility=["private"]))

    assert result == ""
    assert backend.calls == []


@pytest.mark.parametrize(
    ("tenant_id", "user_id", "scope", "visibility"),
    [(None, "u1", "support", ["private"]), ("t1", None, "support", ["private"]), ("t1", "u1", None, ["private"]), ("t1", "u1", "support", [])],
)
def test_memory_retrieval_missing_policy_context_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tenant_id: str | None,
    user_id: str | None,
    scope: str | None,
    visibility: list[str],
) -> None:
    """Missing required policy context fails closed before backend access."""
    monkeypatch.setattr(settings, "LONG_TERM_MEMORY_ENABLED", True)
    backend = FakeMemoryBackend([])
    service = FakeMemoryService(backend)

    result = run(service.search(user_id, "hello", tenant_id=tenant_id, scope=scope, visibility=visibility))

    assert result == ""
    assert backend.calls == []


def test_memory_retrieval_filters_tenant_user_scope_visibility_and_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only fully policy-matching active results are returned."""
    monkeypatch.setattr(settings, "LONG_TERM_MEMORY_ENABLED", True)
    backend = FakeMemoryBackend([
        {"memory": "allowed", "metadata": {"tenant_id": "t1", "user_id": "u1", "scope": "support", "visibility": "private", "active": True}},
        {"memory": "wrong tenant", "metadata": {"tenant_id": "t2", "user_id": "u1", "scope": "support", "visibility": "private", "active": True}},
        {"memory": "wrong user", "metadata": {"tenant_id": "t1", "user_id": "u2", "scope": "support", "visibility": "private", "active": True}},
        {"memory": "wrong scope", "metadata": {"tenant_id": "t1", "user_id": "u1", "scope": "sales", "visibility": "private", "active": True}},
        {"memory": "wrong visibility", "metadata": {"tenant_id": "t1", "user_id": "u1", "scope": "support", "visibility": "public", "active": True}},
        {"memory": "inactive", "metadata": {"tenant_id": "t1", "user_id": "u1", "scope": "support", "visibility": "private", "active": False}},
    ])
    service = FakeMemoryService(backend)

    result = run(service.search("u1", "hello", tenant_id="t1", scope="support", visibility=["private"]))

    assert result == "* allowed"
    assert backend.calls == [{"user_id": "u1", "query": "hello"}]
