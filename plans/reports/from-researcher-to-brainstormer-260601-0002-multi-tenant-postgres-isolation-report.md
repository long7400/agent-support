---
title: Multi-Tenant PostgreSQL Isolation for FastAPI + LangGraph Stack
date: 2026-06-01
status: research-complete
---

# Multi-Tenant PostgreSQL Isolation Report

## Recommendation

**Use PostgreSQL Row-Level Security (RLS) with role-based access control and SET LOCAL tenant context.** This is the only isolation mechanism that prevents accidental cross-tenant queries at the database layer. For your stack (FastAPI + SQLModel + asyncpg + LangGraph + pgvector + Qdrant, 10–100 tenants), RLS is operationally simpler than application-layer filtering and provides defense-in-depth against logic bugs.

**Verdict:** RLS + SET LOCAL is the right choice. Application-layer filtering alone is insufficient for SaaS.

---

## Why for This Stack

**FastAPI + SQLModel + asyncpg:** Async SQLAlchemy 2.0 with asyncpg supports `SET LOCAL` inside transactions. This is the critical enabler—you can set tenant context per request without connection pool pollution.

**LangGraph + PostgresSaver:** LangGraph's checkpointing uses the same database connection pool. RLS policies apply to checkpoint reads/writes, so you must either (a) include tenant_id in checkpoint queries, or (b) use a separate service role with BYPASSRLS for checkpoints. Option (a) is cleaner.

**pgvector + Qdrant:** pgvector queries are RLS-aware. Qdrant is external and tenant-agnostic (you filter results in FastAPI). No conflict.

**10–100 tenants:** RLS scales linearly with policy complexity. At this scale, per-tenant roles are overkill; a single app role + RLS policies is sufficient.

**Multi-tenant SaaS:** RLS is the industry standard for PostgreSQL SaaS (Supabase, Vercel Postgres, etc.). Regulatory compliance (SOC 2, GDPR) expects database-layer isolation.

---

## Implementation Skeleton

### 1. Database Role + RLS Policy (Alembic Migration)

```sql
-- Create app role (least-privileged)
CREATE ROLE app_user WITH LOGIN PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE agent_support TO app_user;

-- Create tenant_id column + RLS policy
ALTER TABLE users ADD COLUMN tenant_id UUID NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE chat_sessions ADD COLUMN tenant_id UUID NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE messages ADD COLUMN tenant_id UUID NOT NULL DEFAULT gen_random_uuid();
-- (repeat for all tables)

-- Enable RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- RLS policy: app_user can only see rows matching current tenant
CREATE POLICY tenant_isolation_users ON users
  USING (tenant_id = current_setting('app.current_tenant')::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation_chat_sessions ON chat_sessions
  USING (tenant_id = current_setting('app.current_tenant')::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);

CREATE POLICY tenant_isolation_messages ON messages
  USING (tenant_id = current_setting('app.current_tenant')::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);

-- Grant table permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON users, chat_sessions, messages TO app_user;
```

### 2. FastAPI Dependency (Set Tenant Context)

```python
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

async def get_current_tenant(request: Request) -> UUID:
    """Extract tenant_id from JWT token or request context."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    
    # Decode JWT, extract tenant_id
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    tenant_id = UUID(payload.get("tenant_id"))
    return tenant_id

async def get_db_with_tenant(
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_current_tenant),
) -> AsyncSession:
    """Open transaction, set tenant context, yield session."""
    async with db.begin():
        # SET LOCAL only works inside a transaction
        await db.execute(
            text("SET LOCAL app.current_tenant = :tenant_id"),
            {"tenant_id": str(tenant_id)}
        )
        yield db
```

---

## Top 5 Gotchas

### 1. asyncpg + Connection Pool Reuse + SET LOCAL Leakage
**Problem:** `SET LOCAL` is transaction-scoped. If you set it outside a transaction or reuse a connection, the setting leaks to the next request.

**Fix:** Always wrap SET LOCAL inside `async with db.begin():` (explicit transaction). Never use `db.execute()` without a transaction context.

### 2. pgbouncer Transaction-Pool Mode Incompatibility
**Problem:** pgbouncer in transaction-pool mode reuses connections between requests. `SET LOCAL` inside a transaction works, but if pgbouncer resets the connection between transactions, the setting is lost.

**Fix:** Use pgbouncer in session-pool mode (one connection per client session), or skip pgbouncer entirely for the app role. For read replicas, use session-pool.

### 3. LangGraph PostgresSaver Doesn't Auto-Set Tenant
**Problem:** LangGraph's `AsyncPostgresSaver` uses the same connection pool but doesn't know about tenant context. Checkpoints are written/read without RLS filtering.

**Fix:** Either (a) include `tenant_id` in checkpoint metadata and filter in application code, or (b) create a separate service role with `BYPASSRLS` for checkpoints and use a different connection pool. Option (a) is simpler.

### 4. pgvector + RLS = Planning Cost Growth
**Problem:** RLS predicates are applied to ANN index scans. The planner must evaluate the predicate for every candidate row, increasing query cost.

**Fix:** This is acceptable for 10–100 tenants. If you hit performance issues, add a partial index: `CREATE INDEX idx_embeddings_tenant ON embeddings USING ivfflat (embedding) WHERE tenant_id = current_setting('app.current_tenant')::uuid;` (requires manual index per tenant or dynamic index creation).

### 5. Operator/Cross-Tenant Queries Need Separate Role
**Problem:** Operators (admins, support staff) need to query across tenants for debugging. RLS blocks them.

**Fix:** Create a separate `operator_role` with `BYPASSRLS` privilege. Use this role only for audited, logged queries. Never use it in application code.

---

## Test Pattern

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest.fixture
async def db_with_tenant():
    """Fixture: least-privileged role, explicit tenant context."""
    engine = create_async_engine(
        "postgresql+asyncpg://app_user:password@localhost/agent_support"
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        async with session.begin():
            await session.execute(
                text("SET LOCAL app.current_tenant = :tenant_id"),
                {"tenant_id": str(TENANT_A_ID)}
            )
            yield session

@pytest.mark.asyncio
async def test_cross_tenant_denial(db_with_tenant):
    """Verify RLS blocks cross-tenant reads."""
    # Insert row as TENANT_A
    await db_with_tenant.execute(
        insert(users).values(tenant_id=TENANT_A_ID, name="Alice")
    )
    
    # Switch context to TENANT_B (new transaction)
    async with db_with_tenant.begin():
        await db_with_tenant.execute(
            text("SET LOCAL app.current_tenant = :tenant_id"),
            {"tenant_id": str(TENANT_B_ID)}
        )
        result = await db_with_tenant.execute(select(users))
        rows = result.fetchall()
        assert len(rows) == 0  # RLS blocks TENANT_A's row
```

---

## Counter-Argument: When RLS Is Wrong

**RLS is wrong if:**
- You have <5 tenants and can afford per-tenant databases (operational simplicity > isolation cost).
- Your queries are so complex that RLS predicates cause unacceptable planner overhead (rare; profile first).
- You need real-time cross-tenant analytics (use a separate data warehouse, not the operational DB).
- Your team lacks PostgreSQL expertise (RLS debugging is harder than application-layer filtering).

**For your case (10–100 tenants, SaaS, compliance-sensitive):** RLS is correct.

---

## Citations

1. [Supabase RLS Guide](https://supabase.com/docs/guides/auth/row-level-security) — Production RLS patterns for multi-tenant SaaS.
2. [PostgreSQL RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) — Official RLS semantics, SET LOCAL scope.
3. [SQLAlchemy 2.0 Async Transactions](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncio-with-an-orm-session) — Async transaction context, connection pool behavior.
4. [asyncpg Connection Pool](https://magicstack.github.io/asyncpg/current/api/index.html#connection-pools) — Connection reuse, transaction isolation.
5. [LangGraph PostgresSaver](https://langchain-ai.github.io/langgraph/reference/checkpointers/#langgraph.checkpoint.postgres.AsyncPostgresSaver) — Checkpoint storage, connection pool usage.
6. [pgvector + RLS Performance](https://github.com/pgvector/pgvector/discussions/156) — ANN index behavior under RLS predicates.

---

**Status: DONE**
