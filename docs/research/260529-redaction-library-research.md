# Research: Redaction and Secret Handling Libraries

Created: 2026-05-29

## Scope

Can this FastAPI/Pydantic/SQLAlchemy project use a library or framework feature
for redaction/secret handling instead of growing custom heuristics?

## Summary

There are useful libraries, but they solve different layers:

- Request schema layer: use Pydantic typed models and `SecretStr`/`SecretBytes`
  when a field is allowed to hold a secret, but not in the current raw plugin
  config phase.
- Persistence boundary: do not rely on redaction. Reject raw credentials and
  store only a credential handle, secret-manager reference, or encrypted
  credential record.
- Logs/telemetry: use a logging/Sentry/observability scrubber.
- PII text redaction: use Presidio or AWS Powertools data masking when the input
  is natural language or user text, not structured plugin config.
- CI/commit scanning: keep `detect-secrets`.

## Options

### Pydantic Secret Types

Best fit: typed plugin schemas and response DTOs.

Pydantic `SecretStr` and `SecretBytes` are designed for values that should not
be visible in logs or tracebacks and serialize as masked values in JSON.

Limits:

- They do not detect arbitrary credential keys in raw JSON.
- The raw value is still intentionally available through `get_secret_value()`.
- They should not be the only persistence control.

Recommendation:

- Do not add `SecretStr`/`SecretBytes` now. The current policy is to reject raw
  credentials before persistence, so there should be no accepted secret field to
  wrap yet.
- Use plugin-specific Pydantic config models.
- For future credential-capable plugins, prefer `credential_ref: UUID | str`
  instead of `api_key: SecretStr`.

### Microsoft Presidio

Best fit: PII detection/anonymization in free text, documents, prompts, or logs.

Presidio has analyzer/anonymizer components and operators such as replace,
redact, hash, mask, and encrypt.

Limits:

- It targets PII text entities, not structured plugin credentials.
- It is heavier than needed for admin config validation.
- False positives/negatives need evaluation data.

Recommendation:

- Consider later for chat transcripts, support tickets, prompt logging, or RAG
  ingestion.
- Do not use it as the primary control for tenant plugin credentials.

### AWS Lambda Powertools Data Masking

Best fit: AWS Lambda/serverless payload masking or encryption.

It can encrypt, decrypt, or irreversibly erase sensitive information.

Limits:

- AWS-specific operational shape.
- More suited to payload masking/encryption pipelines than FastAPI request
  schema validation.

Recommendation:

- Not needed now unless this service moves into Lambda and already uses AWS KMS.

### loggingredactor

Best fit: Python logging filter for regex/key-based redaction.

It supports regex masks, dictionary keys, JSON logs, nested data, positional
arguments, and `extra`.

Limits:

- Small library with limited adoption.
- It protects log output, not request validation or database persistence.

Recommendation:

- Possible later if the project adds structured logging and wants a reusable
  logging filter.
- Keep service-layer redaction utility small until logging architecture exists.

### Sentry Scrubbing / Fillmore

Best fit: error monitoring events.

Sentry supports data scrubbing and SDK `before_send` hooks; Fillmore helps make
Python Sentry event scrubbing easier to configure and test.

Limits:

- Only protects Sentry/error telemetry.
- Does not protect database persistence or API responses by itself.

Recommendation:

- Use if/when Sentry is introduced.
- Prefer client-side `before_send` over sending raw sensitive data and hoping
  server-side scrubbing catches it.

### detect-secrets

Best fit: repo/CI secret scanning.

The project already runs `scripts/check_secret_scan.py`, which is aligned with
this category.

Limits:

- Detects committed secrets, not runtime payloads.

Recommendation:

- Keep it in validation gates.
- Consider baseline plus pre-commit later.

## Recommendation for This Project

Do not replace the current plugin-config guard with a generic redaction library.
The correct boundary is stronger:

1. Reject raw credential-like data before persistence.
2. Keep redaction for response/audit/log defense-in-depth.
3. Move toward a plugin registry with Pydantic config schemas.
4. Introduce a credential store later:
   - `tenant_credentials` table with encryption, or
   - external secret manager such as AWS Secrets Manager, GCP Secret Manager,
     Vault, Doppler, or Infisical.
5. Store only credential handles in `tenant_plugins.config`.

Reminder for future work: add `SecretStr`/`SecretBytes` only when a typed plugin
schema intentionally accepts a secret-like input for immediate handoff into a
credential store. Do not use them as a reason to persist raw secrets inside
`tenant_plugins.config`.

Suggested future shape:

```python
class RagSearchConfig(BaseModel):
    top_k: int = Field(default=5, ge=1, le=50)
    credential_ref: str | None = None

    model_config = ConfigDict(extra="forbid")
```

For the current phase, the custom `secret_like_paths()` guard is acceptable
because it is small, tested, and enforces a product policy rather than trying to
be a universal redaction engine.

## Sources

- Pydantic secret types: https://docs.pydantic.dev/2.2/usage/types/secrets/
- Microsoft Presidio anonymizer: https://microsoft.github.io/presidio/anonymizer/
- AWS Lambda Powertools data masking: https://docs.aws.amazon.com/powertools/python/latest/utilities/data_masking/
- Yelp detect-secrets: https://github.com/Yelp/detect-secrets
- loggingredactor: https://github.com/armurox/loggingredactor
- Sentry data scrubbing: https://docs.sentry.io/product/data-management-settings/scrubbing/
- Fillmore: https://fillmore.readthedocs.io/
