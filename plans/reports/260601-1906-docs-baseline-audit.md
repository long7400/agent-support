---
title: Docs Baseline Audit
date: 2026-06-01
status: baseline-frozen
scope: docs-only
---

# Docs Baseline Audit

## Summary

Docs baseline frozen for Agent Support rebuild. Numbered docs (`docs/00-foundation` through `docs/07-onboarding`) plus `docs/api-reference` are authoritative for implementation planning. Legacy root docs remain as template references only.

No runtime code inspected as implementation target. No runtime code changed.

## Checks Run

| Check | Evidence | Result |
| --- | --- | --- |
| Inventory numbered docs | `find docs -maxdepth 2 -type f -name '*.md'` | 47 authoritative numbered/API docs found. |
| Inventory legacy docs | root `docs/*.md` excluding `docs/README.md` | 13 legacy template docs found. |
| Markdown links/cross-refs | custom markdown link checker over root `README.md`, `docs/**/*.md`, and `plans/reports/*.md` | 65 files checked, 0 broken links. |
| Duplicate/conflict scan | `rg` over template terms and target decisions | Root `README.md` and root `docs/*.md` still describe inherited template. |

## Findings

### F1: Root README still presents template as current

`README.md` begins as "FastAPI LangGraph Agent Template" and points readers to legacy docs. This conflicts with the new docs baseline. Fixed by adding a top-level baseline note pointing to `docs/README.md` and stating numbered docs win.

### F2: Legacy root docs duplicate numbered docs

Files like `docs/system-architecture.md`, `docs/project-roadmap.md`, and `docs/code-standards.md` contain generic/template content that conflicts with Agent Support decisions. Fixed by expanding `docs/README.md` with an explicit legacy-to-authority mapping.

### F3: Decision wording needed precision

`docs/README.md` said 13 decisions live in `06-decisions/`, but only ADR-001..009 live there. Decisions 10..13 are captured in roadmap/foundation docs. Fixed wording to avoid implying missing ADR files.

## Baseline Rules

- Authoritative docs: `docs/00-foundation`, `docs/01-architecture`, `docs/02-persistence`, `docs/03-security`, `docs/04-observability`, `docs/05-roadmap`, `docs/06-decisions`, `docs/07-onboarding`, `docs/api-reference`.
- Legacy docs: root `docs/*.md` except `docs/README.md`.
- Conflict rule: numbered docs win over legacy docs and root `README.md`.
- Next step before runtime code: create Phase 0 implementation plan from `docs/05-roadmap/phase-0-template-hardening.md`.

## Verification

Re-run before Phase 0 code changes:

```bash
python3 -c '<markdown link checker used in audit>'
rg -n "SQLModel|mem0|pgvector|FastAPI LangGraph Agent Template|Project Roadmap" docs README.md
rg -n "[ \t]+$" README.md docs/README.md plans/reports/260601-1906-docs-baseline-audit.md
git diff --check -- README.md docs/README.md plans/reports/260601-1906-docs-baseline-audit.md
```
