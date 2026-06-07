"""P4 knowledge persistence — source, version, document, chunk, sync, audit tables.

Revision ID: c5e7a9b1d3f4
Revises: b4f6d9c1e23f
Create Date: 2026-06-07 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c5e7a9b1d3f4"
down_revision: Union[str, Sequence[str], None] = "b4f6d9c1e23f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

P4_KNOWLEDGE_TABLES = (
    "knowledge_sources",
    "knowledge_source_versions",
    "knowledge_documents",
    "knowledge_chunks",
    "knowledge_sync_jobs",
    "knowledge_ingest_audits",
)


def _create_rls_policy(table_name: str) -> None:
    """Enable and force RLS on tenant-owned tables."""
    op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            f"""
            CREATE POLICY tenant_isolation ON {table_name}
            USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
            """
        )
    )


def upgrade() -> None:
    """Upgrade schema — add P4 knowledge persistence tables."""
    # ---- knowledge_sources ----
    op.create_table(
        "knowledge_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("default_visibility", sa.String(), server_default="private", nullable=False),
        sa.Column("locale", sa.String(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by_actor_type", sa.String(), server_default="operator", nullable=False),
        sa.Column("created_by_actor_id", sa.String(), server_default="system", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source_type IN ('markdown','zip')", name="ck_knowledge_sources_source_type"),
        sa.CheckConstraint("status IN ('active','archived','deleted')", name="ck_knowledge_sources_status"),
        sa.CheckConstraint(
            "default_visibility IN ('public','private','restricted')", name="ck_knowledge_sources_default_visibility"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_knowledge_sources_tenant_slug"),
    )
    op.create_index("idx_knowledge_sources_tenant", "knowledge_sources", ["tenant_id"], unique=False)

    # ---- knowledge_source_versions ----
    op.create_table(
        "knowledge_source_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), server_default="parsing", nullable=False),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("document_count", sa.Integer(), nullable=True),
        sa.Column("embedding_model", sa.String(), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tombstoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_actor_type", sa.String(), server_default="operator", nullable=False),
        sa.Column("created_by_actor_id", sa.String(), server_default="system", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('parsing','chunked','embedded','indexed','verified','active','tombstoned','failed')",
            name="ck_knowledge_source_versions_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_knowledge_source_versions_tenant", "knowledge_source_versions", ["tenant_id"], unique=False)
    op.create_index("idx_knowledge_source_versions_source", "knowledge_source_versions", ["source_id"], unique=False)

    # ---- knowledge_documents ----
    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_version_id"], ["knowledge_source_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_knowledge_documents_tenant", "knowledge_documents", ["tenant_id"], unique=False)
    op.create_index("idx_knowledge_documents_source", "knowledge_documents", ["source_id"], unique=False)
    op.create_index("idx_knowledge_documents_version", "knowledge_documents", ["source_version_id"], unique=False)

    # ---- knowledge_chunks ----
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("section_path", sa.String(), nullable=True),
        sa.Column("source_uri", sa.String(), nullable=True),
        sa.Column("source_title", sa.String(), nullable=True),
        sa.Column("visibility", sa.String(), server_default="private", nullable=False),
        sa.Column("locale", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("lexical_tokens", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("visibility IN ('public','private','restricted')", name="ck_knowledge_chunks_visibility"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_version_id"], ["knowledge_source_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_knowledge_chunks_tenant", "knowledge_chunks", ["tenant_id"], unique=False)
    op.create_index("idx_knowledge_chunks_tenant_source", "knowledge_chunks", ["tenant_id", "source_id"], unique=False)
    op.create_index(
        "idx_knowledge_chunks_tenant_version_active",
        "knowledge_chunks",
        ["tenant_id", "source_version_id", "is_active"],
        unique=False,
    )

    # ---- knowledge_sync_jobs ----
    op.create_table(
        "knowledge_sync_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(), server_default="queued", nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("documents_processed", sa.Integer(), nullable=True),
        sa.Column("chunks_embedded", sa.Integer(), nullable=True),
        sa.Column("vectors_upserted", sa.Integer(), nullable=True),
        sa.Column("lexical_indexed", sa.Integer(), nullable=True),
        sa.Column("errors_count", sa.Integer(), nullable=True),
        sa.Column("error_log", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="ck_knowledge_sync_jobs_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_version_id"], ["knowledge_source_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_knowledge_sync_jobs_tenant_idempotency"),
    )
    op.create_index("idx_knowledge_sync_jobs_tenant", "knowledge_sync_jobs", ["tenant_id"], unique=False)

    # ---- knowledge_ingest_audits ----
    op.create_table(
        "knowledge_ingest_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "detail_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_version_id"], ["knowledge_source_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["knowledge_sync_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_knowledge_ingest_audits_tenant", "knowledge_ingest_audits", ["tenant_id"], unique=False)
    op.create_index("idx_knowledge_ingest_audits_job", "knowledge_ingest_audits", ["job_id"], unique=False)

    # Enable RLS on all P4 tenant-owned tables
    for table_name in P4_KNOWLEDGE_TABLES:
        _create_rls_policy(table_name)


def downgrade() -> None:
    """Downgrade schema — drop P4 knowledge persistence tables."""
    for table_name in reversed(P4_KNOWLEDGE_TABLES):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}"))
        op.execute(sa.text(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"))

    op.drop_index("idx_knowledge_ingest_audits_job", table_name="knowledge_ingest_audits")
    op.drop_index("idx_knowledge_ingest_audits_tenant", table_name="knowledge_ingest_audits")
    op.drop_table("knowledge_ingest_audits")

    op.drop_index("idx_knowledge_sync_jobs_tenant", table_name="knowledge_sync_jobs")
    op.drop_table("knowledge_sync_jobs")

    op.drop_index("idx_knowledge_chunks_tenant_version_active", table_name="knowledge_chunks")
    op.drop_index("idx_knowledge_chunks_tenant_source", table_name="knowledge_chunks")
    op.drop_index("idx_knowledge_chunks_tenant", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

    op.drop_index("idx_knowledge_documents_version", table_name="knowledge_documents")
    op.drop_index("idx_knowledge_documents_source", table_name="knowledge_documents")
    op.drop_index("idx_knowledge_documents_tenant", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")

    op.drop_index("idx_knowledge_source_versions_source", table_name="knowledge_source_versions")
    op.drop_index("idx_knowledge_source_versions_tenant", table_name="knowledge_source_versions")
    op.drop_table("knowledge_source_versions")

    op.drop_index("idx_knowledge_sources_tenant", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
