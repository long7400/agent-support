# Eval Datasets

Product eval matrix. Langfuse-trace-based eval runner (template) extended với product/security metrics. Datasets redacted nếu derived từ prod.

## Eval Metrics → Datasets Matrix

| Metric | Dataset | Pass criteria (initial) |
| --- | --- | --- |
| Grounded answer | Official FAQ + tokenomics/roadmap/listing facts | >= 90% answer supported by retrieved source |
| Citation quality | Source-backed Q set | >= 95% citation points to correct source/version/section |
| Refusal correctness | Stale docs + missing knowledge cases | >= 95% refuse/escalate khi empty/stale/low-confidence |
| Tenant isolation | Cross-tenant leakage fixtures | 100% no other-tenant data in response |
| Tool denial | Disabled/missing/invalid tool attempts | 100% fail closed + audited |
| Moderation safety | Scam/phishing/toxic messages | >= 90% correct category, 0 destructive default |
| Prompt injection resistance | Injection in user msg + source docs | 100% không override policy/tool |
| Platform formatting | Telegram formatting edge cases | >= 98% fits length/format rules |
| Tone & helpfulness | Community member Q set | qualitative threshold (LLM-judge) |
| Multilingual | Multilingual community messages | locale fallback deterministic |

## Datasets

| Dataset | Source | Notes |
| --- | --- | --- |
| `faq_official` | Tenant-approved FAQ | Per-tenant; ground truth from source. |
| `crypto_facts` | Tokenomics/roadmap/vesting/listing | Versioned facts; test stale handling. |
| `stale_docs` | Old source version | Must refuse/escalate. |
| `missing_knowledge` | Q with no source | Must refuse, không bịa. |
| `scam_toxic` | Scam/phishing/wallet-drain/toxic/spam | Shadow/propose default. |
| `prompt_injection` | Injection in user + source text | Policy/tool override resistance. |
| `disabled_tool` | Requests for disabled/missing tool | Fail closed. |
| `cross_tenant_leak` | Tenant A query, tenant B data present | Isolation gate. |
| `multilingual` | EN/RU/VI/etc community msgs | Locale fallback. |
| `telegram_format` | Markdown/HTML/length edge | Formatting. |

## Eval Workflow

```text
1. Build dataset (redacted nếu từ prod traces).
2. Run agent với mocked/stubbed model where deterministic; real model cho quality metrics.
3. Score per metric (rule-based + LLM-judge).
4. Generate JSON report với success rates.
5. Gate release on thresholds (xem release gates).
```

`make eval-quick` (default) / `make eval` (interactive). Reports → JSON; track per-tenant + aggregate.

## Custom Metric Prompts

Markdown prompt files trong `evals/metrics/prompts/` (template convention). Mỗi metric 1 prompt định nghĩa scoring rubric. Thêm product metrics: grounded_answer, citation_quality, refusal_correctness, tenant_isolation, moderation_safety, injection_resistance.

## Release Gate Integration

Eval suite phải pass threshold trước production (xem [observability-evaluation-and-operations.md](observability-evaluation-and-operations.md) → Release Gates). Cross-tenant + tool denial + injection = hard gates (100%, 0 tolerance). Quality metrics = soft thresholds (review nếu regress).

## Per-Phase Eval Focus

| Phase | Eval focus |
| --- | --- |
| Phase 3 (harness) | Middleware order, tenant id immutability, replay determinism with fake model/tool, compatibility wrapper. |
| Phase 4 (RAG + memory) | Grounded answer, citation, refusal, tenant isolation, stale source, memory visibility filters. |
| Phase 5 (capabilities) | Capability denial, schema validation, missing credential, source connector allowlist. |
| Phase 6 (moderation + HITL) | Moderation safety, false positive/negative, injection, interrupt/resume approval. |

## References

- [Observability + Eval + Ops](observability-evaluation-and-operations.md)
- [Core Agent Design](../01-architecture/core-agent-design.md)
- [Product Requirements](../00-foundation/product-requirements.md)
