"""Schema guardrail tests for the six knowledge persistence models."""

import importlib

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeMeta

from app.models.base import Base
from app.models.knowledge_chunk import KnowledgeChunk, CHUNK_VISIBILITIES
from app.models.knowledge_document import KnowledgeDocument
from app.models.knowledge_ingest_audit import KnowledgeIngestAudit
from app.models.knowledge_source import KnowledgeSource, SOURCE_STATUSES, SOURCE_TYPES, SOURCE_VISIBILITIES
from app.models.knowledge_source_version import KnowledgeSourceVersion, VERSION_STATUSES
from app.models.knowledge_sync_job import KnowledgeSyncJob, SYNC_JOB_STATUSES

# All six table names expected in metadata
EXPECTED_TABLES = {
    "knowledge_sources",
    "knowledge_source_versions",
    "knowledge_documents",
    "knowledge_chunks",
    "knowledge_sync_jobs",
    "knowledge_ingest_audits",
}


def _get_columns(model: DeclarativeMeta) -> set[str]:
    """Return column names for a model."""
    return set(model.__table__.columns.keys())


def _get_check_names(model: DeclarativeMeta) -> set[str]:
    """Return CheckConstraint names for a model."""
    return {c.name for c in model.__table__.constraints if isinstance(c, CheckConstraint)}


def _get_index_names(model: DeclarativeMeta) -> set[str]:
    """Return index names for a model."""
    return {i.name for i in model.__table__.indexes}


# ── metadata registration ──────────────────────────────────────────────


def test_metadata_contains_all_knowledge_tables() -> None:
    """Base.metadata includes all six knowledge table names."""
    registered = Base.metadata.tables.keys()
    missing = EXPECTED_TABLES - set(registered)
    assert not missing, f"Tables missing from Base.metadata: {missing}"
    extra = set(registered) & EXPECTED_TABLES
    assert extra == EXPECTED_TABLES, f"Mismatch: {extra.symmetric_difference(EXPECTED_TABLES)}"


# ── model imports are loadable ─────────────────────────────────────────


@pytest.mark.parametrize("module_path", [
    "app.models.knowledge_source",
    "app.models.knowledge_source_version",
    "app.models.knowledge_document",
    "app.models.knowledge_chunk",
    "app.models.knowledge_sync_job",
    "app.models.knowledge_ingest_audit",
])
def test_model_module_imports_cleanly(module_path: str) -> None:
    """Each knowledge model module imports without error."""
    mod = importlib.import_module(module_path)
    assert mod is not None


# ── KnowledgeSource ────────────────────────────────────────────────────


class TestKnowledgeSource:
    """Tests for the KnowledgeSource model."""

    def test_columns(self) -> None:
        """KnowledgeSource has expected columns."""
        cols = _get_columns(KnowledgeSource)
        expected = {
            "id", "tenant_id", "name", "slug", "source_type", "status",
            "default_visibility", "locale", "metadata_json",
            "created_by_actor_type", "created_by_actor_id",
            "created_at",
        }
        assert cols == expected, f"KnowledgeSource columns mismatch: {cols ^ expected}"

    def test_check_constraints(self) -> None:
        """KnowledgeSource has source_type, status, and visibility checks."""
        checks = _get_check_names(KnowledgeSource)
        assert "ck_knowledge_sources_source_type" in checks
        assert "ck_knowledge_sources_status" in checks
        assert "ck_knowledge_sources_default_visibility" in checks

    def test_source_type_check_values(self) -> None:
        """SOURCE_TYPES tuple matches check constraint values."""
        assert SOURCE_TYPES == ("markdown", "zip")

    def test_status_check_values(self) -> None:
        """SOURCE_STATUSES tuple matches check constraint values."""
        assert SOURCE_STATUSES == ("active", "archived", "deleted")

    def test_default_visibility_check_values(self) -> None:
        """SOURCE_VISIBILITIES tuple matches check constraint values."""
        assert SOURCE_VISIBILITIES == ("public", "private", "restricted")

    def test_tenant_id_is_uuid_fk(self) -> None:
        """KnowledgeSource.tenant_id is a UUID FK to tenants."""
        col = KnowledgeSource.__table__.columns["tenant_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.foreign_keys

    def test_id_is_primary_key(self) -> None:
        """KnowledgeSource.id is the primary key."""
        assert KnowledgeSource.__table__.primary_key.columns.keys() == ["id"]

    def test_tenant_index(self) -> None:
        """KnowledgeSource has a tenant_id index."""
        assert "ix_knowledge_sources_tenant_id" in _get_index_names(KnowledgeSource)

    def test_slug_unique_per_tenant(self) -> None:
        """KnowledgeSource slugs are stable tenant-scoped identifiers."""
        constraints = {
            c.name for c in KnowledgeSource.__table__.constraints
            if isinstance(c, UniqueConstraint)
        }
        assert "uq_knowledge_sources_tenant_slug" in constraints

    def test_metadata_is_jsonb(self) -> None:
        """Model type matches the JSONB migration type."""
        assert isinstance(KnowledgeSource.__table__.columns["metadata_json"].type, JSONB)


# ── KnowledgeSourceVersion ─────────────────────────────────────────────


class TestKnowledgeSourceVersion:
    """Tests for the KnowledgeSourceVersion model."""

    def test_columns(self) -> None:
        """KnowledgeSourceVersion has expected columns."""
        cols = _get_columns(KnowledgeSourceVersion)
        expected = {
            "id", "tenant_id", "source_id", "version_number", "status",
            "content_hash", "chunk_count", "document_count",
            "embedding_model", "embedding_dim", "metadata_json",
            "activated_at", "tombstoned_at",
            "created_by_actor_type", "created_by_actor_id",
            "created_at",
        }
        assert cols == expected, f"KnowledgeSourceVersion columns mismatch: {cols ^ expected}"

    def test_check_constraint_exists(self) -> None:
        """KnowledgeSourceVersion has a status check constraint."""
        checks = _get_check_names(KnowledgeSourceVersion)
        assert "ck_knowledge_source_versions_status" in checks

    def test_status_check_values(self) -> None:
        """VERSION_STATUSES matches the check constraint definition."""
        expected = (
            "parsing", "chunked", "embedded", "indexed", "verified",
            "active", "tombstoned", "failed",
        )
        assert VERSION_STATUSES == expected

    def test_tenant_id_is_uuid_fk(self) -> None:
        """KnowledgeSourceVersion.tenant_id is a UUID FK."""
        col = KnowledgeSourceVersion.__table__.columns["tenant_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.foreign_keys

    def test_metadata_is_jsonb(self) -> None:
        """Model type matches the JSONB migration type."""
        assert isinstance(KnowledgeSourceVersion.__table__.columns["metadata_json"].type, JSONB)

    def test_source_id_is_uuid_fk(self) -> None:
        """KnowledgeSourceVersion.source_id is a UUID FK to knowledge_sources."""
        col = KnowledgeSourceVersion.__table__.columns["source_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.foreign_keys

    def test_optional_dates(self) -> None:
        """activated_at and tombstoned_at are nullable."""
        assert KnowledgeSourceVersion.__table__.columns["activated_at"].nullable
        assert KnowledgeSourceVersion.__table__.columns["tombstoned_at"].nullable

    def test_tenant_index(self) -> None:
        """KnowledgeSourceVersion has a tenant_id index."""
        assert "ix_knowledge_source_versions_tenant_id" in _get_index_names(KnowledgeSourceVersion)


# ── KnowledgeDocument ──────────────────────────────────────────────────


class TestKnowledgeDocument:
    """Tests for the KnowledgeDocument model."""

    def test_columns(self) -> None:
        """KnowledgeDocument has expected columns."""
        cols = _get_columns(KnowledgeDocument)
        expected = {
            "id", "tenant_id", "source_id", "source_version_id",
            "filename", "file_type", "file_size_bytes", "content_hash",
            "chunk_count", "metadata_json", "created_at",
        }
        assert cols == expected, f"KnowledgeDocument columns mismatch: {cols ^ expected}"

    def test_tenant_id_is_uuid_fk(self) -> None:
        """KnowledgeDocument.tenant_id is a UUID FK."""
        col = KnowledgeDocument.__table__.columns["tenant_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.foreign_keys

    def test_source_version_id_is_uuid_fk(self) -> None:
        """KnowledgeDocument.source_version_id is a UUID FK."""
        col = KnowledgeDocument.__table__.columns["source_version_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.foreign_keys

    def test_tenant_index(self) -> None:
        """KnowledgeDocument has a tenant_id index."""
        assert "ix_knowledge_documents_tenant_id" in _get_index_names(KnowledgeDocument)

    def test_version_index(self) -> None:
        """KnowledgeDocument has a source_version_id index."""
        assert "ix_knowledge_documents_source_version_id" in _get_index_names(KnowledgeDocument)


# ── KnowledgeChunk ─────────────────────────────────────────────────────


class TestKnowledgeChunk:
    """Tests for the KnowledgeChunk model."""

    def test_columns(self) -> None:
        """KnowledgeChunk has expected columns."""
        cols = _get_columns(KnowledgeChunk)
        expected = {
            "id", "tenant_id", "source_id", "source_version_id",
            "document_id", "chunk_index", "text", "text_hash",
            "token_count", "section_path", "source_uri", "source_title",
            "visibility", "locale", "is_active", "lexical_tokens",
            "metadata_json", "created_at",
        }
        assert cols == expected, f"KnowledgeChunk columns mismatch: {cols ^ expected}"

    def test_required_citation_fields(self) -> None:
        """Verify critical citation and lifecycle fields exist."""
        cols = _get_columns(KnowledgeChunk)
        for field in ("text_hash", "section_path", "visibility", "is_active"):
            assert field in cols, f"Missing required field: {field}"

    def test_check_constraint_exists(self) -> None:
        """KnowledgeChunk has a visibility check constraint."""
        checks = _get_check_names(KnowledgeChunk)
        assert "ck_knowledge_chunks_visibility" in checks

    def test_visibility_check_values(self) -> None:
        """CHUNK_VISIBILITIES matches the check constraint definition."""
        assert CHUNK_VISIBILITIES == ("public", "private", "restricted")

    def test_is_active_default_true(self) -> None:
        """is_active defaults to True."""
        col = KnowledgeChunk.__table__.columns["is_active"]
        assert col.default is not None
        assert col.default.arg is True

    def test_compound_index_tenant_source(self) -> None:
        """Compound index on (tenant_id, source_id)."""
        names = _get_index_names(KnowledgeChunk)
        assert "idx_knowledge_chunks_tenant_source" in names

    def test_compound_index_tenant_version_active(self) -> None:
        """Compound index on (tenant_id, source_version_id, is_active)."""
        names = _get_index_names(KnowledgeChunk)
        assert "idx_knowledge_chunks_tenant_version_active" in names

    def test_text_hash_not_nullable(self) -> None:
        """text_hash is NOT NULL."""
        assert not KnowledgeChunk.__table__.columns["text_hash"].nullable

    def test_section_path_nullable(self) -> None:
        """section_path is nullable."""
        assert KnowledgeChunk.__table__.columns["section_path"].nullable

    def test_tenant_id_is_uuid_fk(self) -> None:
        """KnowledgeChunk.tenant_id is a UUID FK."""
        col = KnowledgeChunk.__table__.columns["tenant_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.foreign_keys


# ── KnowledgeSyncJob ───────────────────────────────────────────────────


class TestKnowledgeSyncJob:
    """Tests for the KnowledgeSyncJob model."""

    def test_columns(self) -> None:
        """KnowledgeSyncJob has expected columns."""
        cols = _get_columns(KnowledgeSyncJob)
        expected = {
            "id", "tenant_id", "source_id", "source_version_id",
            "status", "idempotency_key",
            "started_at", "completed_at",
            "documents_processed", "chunks_embedded",
            "vectors_upserted", "lexical_indexed",
            "errors_count", "error_log",
            "created_at",
        }
        assert cols == expected, f"KnowledgeSyncJob columns mismatch: {cols ^ expected}"

    def test_check_constraint_exists(self) -> None:
        """KnowledgeSyncJob has a status check constraint."""
        checks = _get_check_names(KnowledgeSyncJob)
        assert "ck_knowledge_sync_jobs_status" in checks

    def test_status_check_values(self) -> None:
        """SYNC_JOB_STATUSES matches the check constraint definition."""
        assert SYNC_JOB_STATUSES == ("queued", "running", "succeeded", "failed", "cancelled")

    def test_unique_constraint_tenant_idempotency(self) -> None:
        """Unique constraint on (tenant_id, idempotency_key)."""
        uqs = [
            c for c in KnowledgeSyncJob.__table__.constraints
            if isinstance(c, UniqueConstraint) and set(c.columns.keys()) == {"tenant_id", "idempotency_key"}
        ]
        assert uqs, "Missing UniqueConstraint on (tenant_id, idempotency_key)"

    def test_tenant_index(self) -> None:
        """KnowledgeSyncJob has a tenant_id index."""
        assert "ix_knowledge_sync_jobs_tenant_id" in _get_index_names(KnowledgeSyncJob)

    def test_idempotency_key_not_nullable(self) -> None:
        """idempotency_key is NOT NULL."""
        assert not KnowledgeSyncJob.__table__.columns["idempotency_key"].nullable

    def test_error_log_nullable(self) -> None:
        """error_log is nullable."""
        assert KnowledgeSyncJob.__table__.columns["error_log"].nullable


# ── KnowledgeIngestAudit ───────────────────────────────────────────────


class TestKnowledgeIngestAudit:
    """Tests for the KnowledgeIngestAudit model."""

    def test_columns(self) -> None:
        """KnowledgeIngestAudit has expected columns."""
        cols = _get_columns(KnowledgeIngestAudit)
        expected = {
            "id", "tenant_id", "source_id", "source_version_id",
            "job_id", "event_type", "detail_json", "created_at",
        }
        assert cols == expected, f"KnowledgeIngestAudit columns mismatch: {cols ^ expected}"

    def test_job_id_nullable(self) -> None:
        """job_id is nullable (FK to sync_jobs)."""
        assert KnowledgeIngestAudit.__table__.columns["job_id"].nullable

    def test_tenant_id_is_uuid_fk(self) -> None:
        """KnowledgeIngestAudit.tenant_id is a UUID FK."""
        col = KnowledgeIngestAudit.__table__.columns["tenant_id"]
        assert isinstance(col.type, PG_UUID)
        assert col.foreign_keys

    def test_tenant_index(self) -> None:
        """KnowledgeIngestAudit has a tenant_id index."""
        assert "ix_knowledge_ingest_audits_tenant_id" in _get_index_names(KnowledgeIngestAudit)


# ── Alembic migration round-trip (uses sync engine) ────────────────────


def test_alembic_upgrade_and_downgrade() -> None:
    """Alembic upgrade head then downgrade -1 without error (round-trip).

    Uses the configured test database URL.
    """
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("script_location", "alembic")

    # Upgrade to head (includes our migration)
    command.upgrade(alembic_cfg, "head")

    # Downgrade one step (our migration)
    command.downgrade(alembic_cfg, "-1")

    # Re-upgrade to leave head in place for subsequent tests
    command.upgrade(alembic_cfg, "head")


def test_json_columns_are_jsonb() -> None:
    """All knowledge JSON columns match the migration's PostgreSQL JSONB type."""
    columns = [
        KnowledgeDocument.__table__.columns["metadata_json"],
        KnowledgeChunk.__table__.columns["lexical_tokens"],
        KnowledgeChunk.__table__.columns["metadata_json"],
        KnowledgeSyncJob.__table__.columns["error_log"],
        KnowledgeIngestAudit.__table__.columns["detail_json"],
    ]
    assert all(isinstance(column.type, JSONB) for column in columns)
