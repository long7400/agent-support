# Contribution Flow

Branch → PR → review gates cho Agent Support rebuild.

## Branch Strategy

- `main` — protected, always deployable.
- `feature/<slug>` — new feature/vertical slice.
- `fix/<slug>` — bug fix.
- Push to new branch với `-u`, never directly to main.

## Workflow

```text
1. Pick a phase task (xem 05-roadmap/phase-N-*.md).
2. Read existing implementation + related patterns first.
3. Branch from main.
4. Implement vertical slice (small, focused).
5. Add tests (unit + integration + isolation if tenant-owned).
6. Run local gates (make check + pytest + secret scan).
7. PR with summary + what was tested + blocked features.
8. Pass review gates.
9. Squash merge to main.
```

## PR Requirements

PR description structure:
- **Summary** of changes.
- **What was tested** (commands run, gates passed).
- **Blocked/deferred** features.
- **ADR/PRD references** if decision-relevant.

PR title < 72 chars, conventional commit style.

## Review Gates

Trước merge (CI + reviewer):

| Gate | Check |
| --- | --- |
| Lint | `ruff check .` clean |
| Format | `ruff format --check .` |
| Types | `make typecheck` (pyright) clean |
| Tests | `pytest` pass |
| Migrations | upgrade + downgrade pass (if schema change) |
| Secrets | `detect-secrets` clean |
| Isolation | cross-tenant denial tests (if tenant-owned table) |
| Eval | product eval threshold (if graph/RAG/moderation change) |

## New Tenant-Owned Table Checklist (ADR-002)

Mandatory code review gate khi add tenant-owned table:
- [ ] `tenant_id UUID NOT NULL REFERENCES tenants(id)`.
- [ ] `ENABLE` + `FORCE ROW LEVEL SECURITY`.
- [ ] Policy `USING` + `WITH CHECK`.
- [ ] `GRANT` cho `app_user` (không PUBLIC).
- [ ] Index trên `tenant_id`.
- [ ] Migration upgrade/downgrade.
- [ ] Cross-tenant denial test added.

## Security-Sensitive Changes

Cho auth, RLS, secrets, adapters, moderation enforcement:
- State what was verified + what couldn't be verified.
- Require security-reviewer approval.
- No raw secrets in diff (detect-secrets gate).

## Local Pre-Push

```bash
make check                                          # lint + typecheck
pytest
detect-secrets scan --baseline .secrets.baseline
```

## References

- [Code Standards](code-standards.md)
- [Rebuild Roadmap](../05-roadmap/rebuild-roadmap-and-validation.md)
- [Migration Rules](../02-persistence/migration-rules.md)
