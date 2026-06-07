"""Tests for query rewriting and cache-key uniqueness."""

from uuid import UUID, uuid4

from app.knowledge.cache import build_embedding_cache_key, build_retrieval_cache_key
from app.knowledge.contracts import QueryRewriter
from app.knowledge.query_rewrite import DeterministicQueryRewriter
from app.vector.models import RetrievalMode

# ── DeterministicQueryRewriter ─────────────────────────────────────────


class TestDeterministicQueryRewriter:
    """Whitespace normalisation, safe lowercasing, ID/number/URL preservation."""

    def test_conforms_to_protocol(self) -> None:
        """DeterministicQueryRewriter satisfies the QueryRewriter protocol."""
        assert isinstance(DeterministicQueryRewriter(), QueryRewriter)

    def test_strips_whitespace(self) -> None:
        """Leading and trailing whitespace is removed."""
        rewriter = DeterministicQueryRewriter()
        assert rewriter.rewrite("  hello world  ") == "hello world"

    def test_normalises_internal_spaces(self) -> None:
        """Multiple internal spaces are collapsed to one."""
        rewriter = DeterministicQueryRewriter()
        assert rewriter.rewrite("hello    world   foo") == "hello world foo"

    def test_lowercases_safe_content(self) -> None:
        """Normal text is lowercased."""
        rewriter = DeterministicQueryRewriter()
        assert rewriter.rewrite("Hello World") == "hello world"

    def test_preserves_numbers(self) -> None:
        """Numeric values are preserved."""
        rewriter = DeterministicQueryRewriter()
        assert rewriter.rewrite("version 2.5 is better") == "version 2.5 is better"

    def test_preserves_percentages(self) -> None:
        """Percentage values are preserved."""
        rewriter = DeterministicQueryRewriter()
        result = rewriter.rewrite("increase by 25%")
        assert "25%" in result

    def test_preserves_urls(self) -> None:
        """URLs are preserved with original casing."""
        rewriter = DeterministicQueryRewriter()
        text = "Check https://Example.com/Path for docs"
        result = rewriter.rewrite(text)
        assert "https://Example.com/Path" in result

    def test_preserves_tickers(self) -> None:
        """Stock/crypto tickers ($AAPL, $BTC) are preserved."""
        rewriter = DeterministicQueryRewriter()
        result = rewriter.rewrite("What is $BTC price")
        assert "$BTC" in result

    def test_preserves_hex_ids(self) -> None:
        """Hex identifiers (0x...) are preserved."""
        rewriter = DeterministicQueryRewriter()
        result = rewriter.rewrite("tx 0xAbCdEf123456")
        assert "0xAbCdEf123456" in result

    def test_preserves_uuids(self) -> None:
        """UUIDs are preserved with original casing."""
        rewriter = DeterministicQueryRewriter()
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        result = rewriter.rewrite(f"doc {uuid_str} is important")
        assert uuid_str in result

    def test_empty_input(self) -> None:
        """Empty string returns empty string."""
        rewriter = DeterministicQueryRewriter()
        assert rewriter.rewrite("") == ""
        assert rewriter.rewrite("   ") == ""

    def test_deterministic(self) -> None:
        """Same input always produces the same output."""
        rewriter = DeterministicQueryRewriter()
        text = "  HELLO   WORLD 123  "
        assert rewriter.rewrite(text) == rewriter.rewrite(text)

    def test_mixed_content(self) -> None:
        """Mixed safe content and preserve tokens works correctly."""
        rewriter = DeterministicQueryRewriter()
        result = rewriter.rewrite("  Check $BTC at https://Example.com 123  ")
        # Leading/trailing trimmed, internal spaces merged, safe content lowered,
        # preserve tokens unchanged
        assert result.startswith("check")
        assert "$BTC" in result
        assert "https://Example.com" in result
        assert "123" in result


# ── Cache key helpers ──────────────────────────────────────────────────


class TestEmbeddingCacheKey:
    """Embedding cache key composition and uniqueness."""

    def test_key_differs_by_tenant(self) -> None:
        """Same text produces different keys for different tenants."""
        tid_a = uuid4()
        tid_b = uuid4()
        text = "hello world"

        key_a = build_embedding_cache_key(tid_a, text, "model-v1")
        key_b = build_embedding_cache_key(tid_b, text, "model-v1")

        assert key_a != key_b

    def test_key_differs_by_text(self) -> None:
        """Different texts produce different keys for same tenant."""
        tid = uuid4()

        key_a = build_embedding_cache_key(tid, "hello", "model-v1")
        key_b = build_embedding_cache_key(tid, "world", "model-v1")

        assert key_a != key_b

    def test_key_differs_by_model(self) -> None:
        """Different embedding models produce different keys."""
        tid = uuid4()
        text = "hello world"

        key_a = build_embedding_cache_key(tid, text, "model-v1")
        key_b = build_embedding_cache_key(tid, text, "model-v2")

        assert key_a != key_b

    def test_key_differs_by_version(self) -> None:
        """Different embedding versions produce different keys."""
        tid = uuid4()
        text = "hello world"

        key_a = build_embedding_cache_key(tid, text, "model-v1", embedding_version="1.0")
        key_b = build_embedding_cache_key(tid, text, "model-v1", embedding_version="2.0")

        assert key_a != key_b

    def test_same_input_same_key(self) -> None:
        """Same inputs always produce the same key (deterministic)."""
        tid = uuid4()
        text = "hello world"

        key_a = build_embedding_cache_key(tid, text, "model-v1")
        key_b = build_embedding_cache_key(tid, text, "model-v1")

        assert key_a == key_b

    def test_key_prefix(self) -> None:
        """Cache key starts with 'emb:' prefix."""
        key = build_embedding_cache_key(uuid4(), "hello", "m1")
        assert key.startswith("emb:")


class TestRetrievalCacheKey:
    """Retrieval cache key composition and uniqueness."""

    def test_key_differs_by_tenant(self) -> None:
        """Same query produces different keys for different tenants."""
        tid_a = uuid4()
        tid_b = uuid4()

        key_a = build_retrieval_cache_key(tid_a, "hello", RetrievalMode.hybrid)
        key_b = build_retrieval_cache_key(tid_b, "hello", RetrievalMode.hybrid)

        assert key_a != key_b

    def test_key_differs_by_retrieval_mode(self) -> None:
        """Different retrieval modes produce different keys."""
        tid = uuid4()
        query = "hello"

        key_hybrid = build_retrieval_cache_key(tid, query, RetrievalMode.hybrid)
        key_vector = build_retrieval_cache_key(tid, query, RetrievalMode.vector)
        key_keyword = build_retrieval_cache_key(tid, query, RetrievalMode.keyword)

        assert len({key_hybrid, key_vector, key_keyword}) == 3

    def test_key_differs_by_source_version(self) -> None:
        """Different source version scopes produce different keys."""
        tid = uuid4()
        sv_a = [uuid4()]
        sv_b = [uuid4()]

        key_a = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, source_version_ids=sv_a)
        key_b = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, source_version_ids=sv_b)

        assert key_a != key_b

    def test_key_differs_by_visibility(self) -> None:
        """Different visibility filters produce different keys."""
        tid = uuid4()

        key_a = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, visibility=["public"])
        key_b = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, visibility=["private"])

        assert key_a != key_b

    def test_key_differs_by_locale(self) -> None:
        """Different locale filters produce different keys."""
        tid = uuid4()

        key_a = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, locale="en")
        key_b = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, locale="vi")

        assert key_a != key_b

    def test_key_differs_by_top_k(self) -> None:
        """Different top-k values produce different keys."""
        tid = uuid4()

        key_a = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, candidate_top_k=50)
        key_b = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, candidate_top_k=100)

        assert key_a != key_b

    def test_key_differs_by_min_score(self) -> None:
        """Different min_score values produce different keys."""
        tid = uuid4()

        key_a = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, min_score=0.0)
        key_b = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, min_score=0.5)

        assert key_a != key_b

    def test_same_input_same_key(self) -> None:
        """Same inputs always produce the same key (deterministic)."""
        tid = uuid4()

        key_a = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid)
        key_b = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid)

        assert key_a == key_b

    def test_key_differs_by_query_text_same_tenant(self) -> None:
        """Different query texts with same tenant produce different keys."""
        tid = uuid4()

        key_a = build_retrieval_cache_key(tid, "hello world", RetrievalMode.hybrid)
        key_b = build_retrieval_cache_key(tid, "goodbye world", RetrievalMode.hybrid)

        assert key_a != key_b

    def test_key_prefix(self) -> None:
        """Cache key starts with 'ret:' prefix."""
        key = build_retrieval_cache_key(uuid4(), "hello", RetrievalMode.hybrid)
        assert key.startswith("ret:")

    def test_embedding_model_in_key(self) -> None:
        """Embedding model parameter affects the key."""
        tid = uuid4()

        key_a = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, embedding_model="model-v1")
        key_b = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, embedding_model="model-v2")

        assert key_a != key_b

    def test_multiple_source_versions_ordered(self) -> None:
        """Source version IDs are sorted for deterministic ordering."""
        tid = uuid4()
        sv_a = [UUID("00000000-0000-0000-0000-000000000001")]
        sv_b = [UUID("00000000-0000-0000-0000-000000000002")]

        key_a = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, source_version_ids=sv_a)
        key_b = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, source_version_ids=sv_b)

        assert key_a != key_b


class TestCrossTenantCacheKeyUniqueness:
    """Cache keys guarantee uniqueness across tenants and source versions."""

    def test_embedding_key_tenant_isolation(self) -> None:
        """Same embedding input for different tenants -> different keys."""
        tid_a = uuid4()
        tid_b = uuid4()
        text = "identical query text"

        key_a = build_embedding_cache_key(tid_a, text, "m1")
        key_b = build_embedding_cache_key(tid_b, text, "m1")

        assert key_a != key_b, "cache keys must differ across tenants"

    def test_retrieval_key_tenant_isolation(self) -> None:
        """Same retrieval input for different tenants -> different keys."""
        tid_a = uuid4()
        tid_b = uuid4()

        key_a = build_retrieval_cache_key(tid_a, "hello", RetrievalMode.hybrid)
        key_b = build_retrieval_cache_key(tid_b, "hello", RetrievalMode.hybrid)

        assert key_a != key_b, "cache keys must differ across tenants"

    def test_retrieval_key_source_version_isolation(self) -> None:
        """Same retrieval input, different source versions -> different keys."""
        tid = uuid4()
        sv_a = [uuid4()]
        sv_b = [uuid4()]

        key_a = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, source_version_ids=sv_a)
        key_b = build_retrieval_cache_key(tid, "hello", RetrievalMode.hybrid, source_version_ids=sv_b)

        assert key_a != key_b, "cache keys must differ across source versions"

    def test_all_mode_keys_differ(self) -> None:
        """All three retrieval modes produce distinct keys for same input."""
        tid = uuid4()
        keys = {
            build_retrieval_cache_key(tid, "test", RetrievalMode.hybrid),
            build_retrieval_cache_key(tid, "test", RetrievalMode.vector),
            build_retrieval_cache_key(tid, "test", RetrievalMode.keyword),
        }
        assert len(keys) == 3, "all three retrieval modes must produce unique keys"
