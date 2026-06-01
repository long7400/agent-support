# Admin API

Tenant admin/operator endpoints. Auth: JWT user + tenant role (ADR-005). All routes rate-limited. Prefix `/api/v1` (template convention).

> Manual contract reference. Source of truth = FastAPI OpenAPI (`/docs`). Update khi routes thay đổi.

## Auth

| Header | Use |
| --- | --- |
| `Authorization: Bearer <jwt>` | Human admin (membership role) |
| `X-Service-Key: <key>` | Service principal (automation, scoped) |

Role required noted per endpoint. Tenant context resolved từ membership; `SET LOCAL` applied.

## Tenant Lifecycle (operator)

### Create tenant
`POST /v1/admin/tenants` — role: operator
```json
{ "slug": "my-project", "display_name": "My Project" }
```
→ `201 { "id": "uuid", "status": "active" }`. Audit: `tenant.created`.

### Get / update tenant config
`GET /v1/admin/tenants/{id}` — role: admin/viewer
`PATCH /v1/admin/tenants/{id}` — role: admin (versioned)
```json
{ "persona": {...}, "official_links": [...], "moderation_mode": "shadow", "model_budget": {...} }
```
→ new `tenant_config_versions` row. Audit: `tenant.config_updated` (before/after, config_version).

### Tenant status
`POST /v1/admin/tenants/{id}/status` — role: operator
```json
{ "status": "active|disabled|suspended|deleting" }
```
Disabled → runtime blocked. Deleting → GDPR flow (runbook 7).

## Membership (admin)

### Invite/assign member
`POST /v1/admin/tenants/{id}/members` — role: admin
```json
{ "user_id": "uuid", "role": "admin|moderator|viewer" }
```

### List members
`GET /v1/admin/tenants/{id}/members` — role: admin

## Service Principals (admin, ADR-005)

### Generate key
`POST /v1/admin/tenants/{id}/service-principals` — role: admin
```json
{ "name": "ci-deploy", "scopes": ["source:write"] }
```
→ `201 { "id": "uuid", "key": "<show once>" }`. Stored as `key_hash`. Audit: `service_principal.created`.

### Revoke
`POST /v1/admin/service-principals/{id}/revoke` — role: admin

## Telegram Setup (admin, ADR-009)

### Submit bot token
`POST /v1/admin/telegram/setup` — role: admin
```json
{ "bot_token": "<from BotFather>" }
```
Backend: validate `getMe` → KMS encrypt → `tenant_platforms` + credential handle → `setWebhook(secret_token)`. Audit: `adapter_credential.created`. Token never returned/logged.

### Confirm channel mapping
`POST /v1/admin/telegram/channels/{id}/confirm` — role: admin

## Knowledge Sources (admin, Phase 4)

### Upload source
`POST /v1/admin/tenants/{id}/sources` — role: admin (multipart .md/.zip)
→ creates `knowledge_source_versions(parsing)` + sync job. Audit: `knowledge_source.created`.

### Get sync status
`GET /v1/admin/sources/{id}/sync` — role: admin/viewer
→ status, counts, redacted error.

### Activate / tombstone
`POST /v1/admin/source-versions/{id}/activate` — role: admin (after verify)
`POST /v1/admin/source-versions/{id}/tombstone` — role: admin

### Review candidate
`POST /v1/admin/candidates/{id}/decision` — role: moderator
```json
{ "decision": "approve|reject" }
```

## Capabilities (admin, Phase 5)

### Enable/disable capability
`POST /v1/admin/tenants/{id}/capabilities` — role: admin
```json
{ "capability_name": "rag.search", "enabled": true }
```

### Set tool policy
`PUT /v1/admin/tenants/{id}/tool-policies/{capability}` — role: admin
```json
{ "timeout_ms": 3000, "budget": {...}, "rate_limit": {...}, "approval_required": false }
```

## Moderation Review (Phase 6)

### Queue
`GET /v1/admin/moderation/queue` — role: moderator
### Decision
`POST /v1/admin/moderation/{id}/decision` — role: moderator
```json
{ "action": "approve|reject|escalate" }
```
(Telegram bot review = alternate path, Decision 12.)

## Error Format

```json
{ "error_code": "TENANT_DISABLED", "detail": "…", "trace_id": "uuid" }
```

## References

- [Authn/Authz](../03-security/authn-authz.md)
- [Adapter Ingest API](adapter-ingest-api.md)
- [Operator API](operator-api.md)
- [Phase 1 Tenant Control Plane](../05-roadmap/phase-1-tenant-control-plane.md)
