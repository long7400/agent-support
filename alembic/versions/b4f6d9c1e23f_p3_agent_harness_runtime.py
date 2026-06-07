"""P3 agent harness runtime — run, step, model call, and checkpoint metadata tables.

Revision ID: b4f6d9c1e23f
Revises: a3f5c8e12d47
Create Date: 2026-06-07 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b4f6d9c1e23f"
down_revision: Union[str, Sequence[str], None] = "a3f5c8e12d47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

P3_TENANT_OWNED_TABLES = (
    "agent_runs",
    "agent_run_steps",
    "model_calls",
    "graph_checkpoint_metadata",
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
    """Upgrade schema — add P3 agent harness runtime tables."""
    # agent_runs: record of one harness agent execution
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("processing_outbox_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("input_event_id", sa.String(), nullable=False),
        sa.Column("harness_version", sa.String(), nullable=False),
        sa.Column(
            "middleware_sequence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("config_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("policy_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("final_response_preview", sa.String(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','denied','failed','interrupted')",
            name="ck_agent_runs_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["processing_outbox_id"], ["processing_outbox.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_agent_runs_tenant", "agent_runs", ["tenant_id"], unique=False)
    op.create_index("idx_agent_runs_status", "agent_runs", ["status", "created_at"], unique=False)

    # agent_run_steps: individual step within an agent run
    op.create_table(
        "agent_run_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(), nullable=False),
        sa.Column("step_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="completed", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("redacted_summary", sa.String(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "step_type IN ('middleware','model','tool','capability')",
            name="ck_agent_run_steps_step_type",
        ),
        sa.CheckConstraint(
            "status IN ('completed','failed','denied','interrupted')",
            name="ck_agent_run_steps_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_agent_run_steps_tenant", "agent_run_steps", ["tenant_id"], unique=False)
    op.create_index("idx_agent_run_steps_run", "agent_run_steps", ["agent_run_id", "step_order"], unique=False)

    # model_calls: record of one LLM model invocation
    op.create_table(
        "model_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("mock_cost", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), server_default="completed", nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('completed','failed','timeout','denied')",
            name="ck_model_calls_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["agent_run_steps.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_model_calls_tenant", "model_calls", ["tenant_id"], unique=False)
    op.create_index("idx_model_calls_run", "model_calls", ["agent_run_id"], unique=False)

    # graph_checkpoint_metadata: maps checkpoint data to tenant/run context
    op.create_table(
        "graph_checkpoint_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checkpoint_id", sa.String(), nullable=False),
        sa.Column(
            "checkpoint_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_checkpoint_metadata_tenant", "graph_checkpoint_metadata", ["tenant_id"], unique=False)
    op.create_index(
        "idx_checkpoint_metadata_thread", "graph_checkpoint_metadata", ["thread_id", "checkpoint_id"], unique=False
    )

    # Enable RLS on all P3 tenant-owned tables
    for table_name in P3_TENANT_OWNED_TABLES:
        _create_rls_policy(table_name)


def downgrade() -> None:
    """Downgrade schema — drop P3 agent harness runtime tables."""
    for table_name in reversed(P3_TENANT_OWNED_TABLES):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}"))
        op.execute(sa.text(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY"))
    op.drop_index("idx_checkpoint_metadata_thread", table_name="graph_checkpoint_metadata")
    op.drop_index("idx_checkpoint_metadata_tenant", table_name="graph_checkpoint_metadata")
    op.drop_table("graph_checkpoint_metadata")
    op.drop_index("idx_model_calls_run", table_name="model_calls")
    op.drop_index("idx_model_calls_tenant", table_name="model_calls")
    op.drop_table("model_calls")
    op.drop_index("idx_agent_run_steps_run", table_name="agent_run_steps")
    op.drop_index("idx_agent_run_steps_tenant", table_name="agent_run_steps")
    op.drop_table("agent_run_steps")
    op.drop_index("idx_agent_runs_status", table_name="agent_runs")
    op.drop_index("idx_agent_runs_tenant", table_name="agent_runs")
    op.drop_table("agent_runs")
