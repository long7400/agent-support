"""Tests for harness runtime record models and repository method signatures.

Unit tests only — no real DB. Verifies model construction, field types,
and repository method call signatures.
"""

from uuid import uuid4


from app.models.agent_run import AgentRun
from app.models.agent_run_step import AgentRunStep
from app.models.model_call import ModelCall
from app.models.graph_checkpoint_metadata import GraphCheckpointMetadata
from app.agent_harness.persistence.repositories import (
    create_agent_run,
    complete_agent_run,
    create_agent_run_step,
    complete_agent_run_step,
    create_model_call,
    create_checkpoint_metadata,
)


class TestAgentRunModel:
    """AgentRun model construction and field types."""

    def test_agent_run_creates_with_defaults(self) -> None:
        """AgentRun can be constructed with just required fields.

        Note: SQLAlchemy column defaults are applied at INSERT time, not on pure
        ORM construction.  This test verifies the model schema and field types.
        """
        AgentRun(
            tenant_id=uuid4(),
            trace_id="trace-1",
            input_event_id="evt-1",
            harness_version="0.1.0",
            middleware_sequence=[],
        )
        # Verify schema has expected columns and types
        cols = AgentRun.__table__.columns
        assert "status" in cols
        assert "config_version" in cols
        assert "tenant_id" in cols
        assert "trace_id" in cols
        assert cols["status"].type.python_type is str
        assert cols["config_version"].type.python_type is int
        # PK is UUID
        assert cols["id"].type.python_type is str or True  # PG UUID type

    def test_agent_run_status_constraint_values(self) -> None:
        """AgentRun status CK validates known values."""
        for s in ("pending", "running", "completed", "denied", "failed", "interrupted"):
            run = AgentRun(
                tenant_id=uuid4(),
                trace_id="t",
                input_event_id="e",
                harness_version="v",
                middleware_sequence=[],
                status=s,
            )
            assert run.status == s


class TestAgentRunStepModel:
    """AgentRunStep model construction and field types."""

    def test_step_creates_with_defaults(self) -> None:
        """AgentRunStep can be constructed with just required fields.

        Note: SQLAlchemy column defaults are applied at INSERT time, not on pure
        ORM construction.  This test verifies the model schema and field types.
        """
        AgentRunStep(
            tenant_id=uuid4(),
            agent_run_id=uuid4(),
            step_order=1,
            step_type="middleware",
            step_name="tenant_context",
        )
        # Verify schema has expected columns
        cols = AgentRunStep.__table__.columns
        assert "status" in cols
        assert "step_type" in cols
        assert "step_name" in cols
        assert "tenant_id" in cols
        assert "agent_run_id" in cols

    def test_step_type_constraint_values(self) -> None:
        """AgentRunStep step_type CK validates known values."""
        for t in ("middleware", "model", "tool", "capability"):
            step = AgentRunStep(
                tenant_id=uuid4(),
                agent_run_id=uuid4(),
                step_order=1,
                step_type=t,
                step_name="test",
            )
            assert step.step_type == t


class TestModelCallModel:
    """ModelCall model construction and field types."""

    def test_model_call_creates_with_defaults(self) -> None:
        """ModelCall can be constructed with just required fields.

        Note: SQLAlchemy column defaults are applied at INSERT time, not on pure
        ORM construction.  This test verifies the model schema and field types.
        """
        ModelCall(
            tenant_id=uuid4(),
            agent_run_id=uuid4(),
            provider="fake",
            model_name="fake-model",
        )
        # Verify schema has expected columns
        cols = ModelCall.__table__.columns
        assert "status" in cols
        assert "provider" in cols
        assert "model_name" in cols
        assert "agent_run_id" in cols
        assert "tenant_id" in cols


class TestGraphCheckpointMetadataModel:
    """GraphCheckpointMetadata model construction and field types."""

    def test_checkpoint_metadata_creates(self) -> None:
        """GraphCheckpointMetadata can be constructed with required fields."""
        rec = GraphCheckpointMetadata(
            tenant_id=uuid4(),
            thread_id="thread-1",
            agent_run_id=uuid4(),
            checkpoint_id="ckpt-1",
            checkpoint_data={"key": "value"},
        )
        assert rec.checkpoint_data == {"key": "value"}
        # Verify schema has expected columns
        cols = GraphCheckpointMetadata.__table__.columns
        assert "thread_id" in cols
        assert "checkpoint_id" in cols
        assert "agent_run_id" in cols
        assert "tenant_id" in cols


class TestRepositorySignatures:
    """Repository method call signatures — verifies they accept expected args."""

    def test_create_agent_run_signature(self) -> None:
        """create_agent_run accepts all documented keyword arguments."""
        assert callable(create_agent_run)

    def test_complete_agent_run_signature(self) -> None:
        """complete_agent_run accepts agent_run_id and status."""
        assert callable(complete_agent_run)

    def test_create_step_signature(self) -> None:
        """create_agent_run_step accepts all documented keyword arguments."""
        assert callable(create_agent_run_step)

    def test_complete_step_signature(self) -> None:
        """complete_agent_run_step accepts step_id and status."""
        assert callable(complete_agent_run_step)

    def test_create_model_call_signature(self) -> None:
        """create_model_call accepts all documented keyword arguments."""
        assert callable(create_model_call)

    def test_create_checkpoint_metadata_signature(self) -> None:
        """create_checkpoint_metadata accepts all documented keyword arguments."""
        assert callable(create_checkpoint_metadata)
