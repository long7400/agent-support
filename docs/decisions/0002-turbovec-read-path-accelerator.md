# ADR 0002: TurboVec Read-Path Accelerator

## Status

Proposed.

## Context

`spec.md` names `LlamaIndex + TurboVec` as the fast RAG read path. Follow-up research on `RyanCodrai/turbovec` shows it is a serious candidate:

- Rust vector index with Python bindings.
- PyPI package `turbovec`, verified at version `0.6.0` on 2026-05-28.
- LlamaIndex integration via `turbovec.llama_index.TurboQuantVectorStore`.
- `IdMapIndex` for stable external ids.
- Search-time allowlist filtering.
- Async LlamaIndex methods.
- Local persist/load through `.tvim` binary index plus JSON side-car.

The same research also shows production caveats:

- PyPI classifier is `Development Status :: 3 - Alpha`.
- It is a local index library, not a managed vector database.
- Persistence is local filesystem oriented.
- MMR is not supported.
- Full-precision embeddings are not recoverable from the compressed index.
- Metadata must be JSON-serializable.

## Decision

Use Qdrant as the durable vector store and evaluate TurboVec as an optional read-path accelerator.

The accepted runtime shape is:

```text
Knowledge sync
  -> durable chunks and embeddings in Qdrant
  -> optional TurboVec local index build

RAG query
  -> tenant/source ACL resolution
  -> Qdrant baseline retrieval
  -> optional TurboVec candidate retrieval or rerank path
  -> citation builder
  -> answer generation
```

TurboVec must be behind a feature flag:

```text
RAG_ACCELERATOR=none|turbovec
```

## Adoption Flow

1. Implement the Qdrant baseline first.
2. Add a `VectorSearchProvider` interface.
3. Implement `QdrantVectorSearchProvider`.
4. Implement `TurboVecVectorSearchProvider` as an optional provider.
5. Build the same tenant/source filter contract for both providers.
6. Run benchmark and quality evaluation on the same fixture corpus.
7. Run persist/load and rebuild tests.
8. Run fallback test: TurboVec failure must fall back to Qdrant or fail closed.
9. Promote from proposed to accepted only after gates pass.

## Required Gates

| Gate | Requirement |
| --- | --- |
| Correctness | Top-k results are tenant-filtered and citation metadata is intact. |
| Quality | Recall and answer quality are equal or better than Qdrant baseline on project fixtures. |
| Latency | p95 retrieval latency improves enough to justify extra operational surface. |
| Memory | RAM usage reduction is measured on realistic corpus size. |
| Rebuild | Index can be rebuilt from Qdrant/source chunks without manual repair. |
| Persistence | Persist/load works in local and deployed runtime layout. |
| Fallback | Feature flag can disable TurboVec without data migration. |
| Operations | Metrics show accelerator hit rate, build time, load time, errors, and fallback count. |

## Consequences

- Team can experiment with TurboVec without blocking v1.
- Qdrant remains the source of truth for vectors and metadata.
- TurboVec code must be isolated behind an interface and feature flag.
- If TurboVec passes gates, update this ADR to `Accepted` and update `technical-plan.md`.
