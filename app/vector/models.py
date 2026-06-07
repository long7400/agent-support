"""Pydantic models for vector retrieval queries."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class RetrievalMode(str, Enum):
    """Search execution mode for the retrieval pipeline."""

    hybrid = "hybrid"
    vector = "vector"
    keyword = "keyword"


class RetrievalQuery(BaseModel):
    """Typed query contract for the retrieval pipeline.

    Every retrieval request through the harness is serialised as a
    ``RetrievalQuery`` so middleware can validate tenant boundaries,
    budget, and visibility before the provider is called.
    """

    tenant_id: UUID = Field(
        ...,
        description="Mandatory tenant scope. Providers MUST reject the zero UUID.",
    )
    query_text: str = Field(default="", description="Raw user query text.")
    embedding: list[float] = Field(
        default_factory=list,
        description="Pre-computed query embedding (optional).",
    )
    retrieval_mode: RetrievalMode = Field(
        default=RetrievalMode.hybrid,
        description="Which search pipeline to execute.",
    )
    candidate_top_k: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Number of raw candidates to fetch from each provider.",
    )
    final_top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of results to return after fusion / reranking.",
    )
    min_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum similarity or relevance score threshold.",
    )
    visibility: list[str] = Field(
        default_factory=lambda: ["public"],
        description="Allowed visibility levels (e.g. public, private, restricted).",
    )
    source_allowlist: list[UUID] | None = Field(
        default=None,
        description="Optional list of source UUIDs to restrict search scope.",
    )
    locale: str | None = Field(
        default=None,
        description="Optional locale filter (e.g. 'en', 'vi').",
    )
    active_only: bool = Field(
        default=True,
        description="Only search active (non-tombstoned) chunks.",
    )
    source_version_ids: list[UUID] | None = Field(
        default=None,
        description="Optional list of source version UUIDs to scope search.",
    )

    model_config = {"frozen": True}
