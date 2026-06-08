# ADR-004: ORM Choice

- **Status:** accepted
- **Date:** 2026-06-01
- **Deciders:** eng-lead, backend-eng, db-eng
- **Related:** ADR-002, [persistence-strategy.md](../02-persistence/persistence-strategy.md)

## Context

Template dùng SQLModel (mix Pydantic + SQLAlchemy) với 1 connection user, không RLS. Quyết định ORM ảnh hưởng mọi schema/repository code Phase 1+. ADR-002 chốt RLS toàn diện; research implementation skeleton viết bằng SQLAlchemy 2.0 async. Domain schema ~15-20 bảng.

## Decision

**Migrate sang SQLAlchemy 2.0 thuần + Pydantic v2 riêng ngay Phase 0.** Tách persistence model (ORM) khỏi API DTO (Pydantic).

## Consequences

### Positive
- RLS docs/pattern production-grade cho SQLAlchemy 2.0 (không có cho SQLModel).
- Mature, full async support (asyncpg).
- Tách rõ persistence model vs API DTO (data ownership principle).

### Negative / Costs
- Refactor template auth/session/database modules (~1-2 tuần Phase 0).
- Maintain 2 layer (ORM model + Pydantic schema).

### Follow-up actions
- Replace SQLModel base với `DeclarativeBase` + `Mapped[]` (Phase 0).
- Pydantic v2 schemas riêng cho API DTO.
- Không return ORM object trực tiếp.
- Alembic raw SQL cho RLS (ADR-002).

## Alternatives Considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Giữ SQLModel | Template-native, ít refactor | RLS pattern thiếu, mix Pydantic v2 + SQLAlchemy rough, leak field risk | rejected |
| **SQLAlchemy 2.0 thuần** | Mature, RLS docs, DTO separation | Refactor template, 2 layer | **chosen** |
| Hybrid (SQLModel legacy + SQLAlchemy domain) | Không động template | 2 ORM pattern = học cost + confusion | rejected |

## Notes

Phase 0 là đúng thời điểm migrate (Phase 1+ chỉ 2 file template chạm: auth.py + session model). Counter-argument: nếu team ít người + ship MVP 2-3 tuần thì giữ SQLModel — nhưng compliance + multi-tenant SaaS không phải MVP "ship nhanh".
