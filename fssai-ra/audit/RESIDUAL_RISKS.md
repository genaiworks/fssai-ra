# Residual risks and qualification gates

This is a completed local revision and bounded experiment package, not institutional deployment qualification. The audit did not exhaust every attack class or production integration.

| Priority | Risk / gate | Evidence and current verdict | Required owner/action |
|---|---|---|---|
| P0 | Hostile generated code bypasses Python boundaries | Same-OS-user subprocess directly read the synthetic database. No isolation claim survives this probe. | Platform/security: isolate actual service accounts, mounts, ports, credentials, model runtime and every worker; execute target-identity probes. |
| P0 | Authentic bad policy/source or colluding reviewers | Executed wrong authoritative-source case produces wrong grade with real approval; appeal repairs local record. | Domain owner: independently validate source correctness and appeals; separate administrator/reviewer powers. |
| P0 | Production identity/key configuration | Doctor reports public teaching keys/tokens and volatile original service state. Joined operational profile refuses startup. | IAM/operations: provision protected keys and entitlements, external authentication and explicit tenant policy. |
| P0 | Unqualified wider routes | Existing HTTP/action/disclosure tests run, but joined SQLite guarantees do not automatically cover all API routes, workers, tool adapters or model-serving processes. | Service owners: inventory-to-test mapping on actual deployment. |
| P1 | External effects / streaming / arbitrary memory | Not implemented in joined JSON interface; attempts deny. No remote reconciliation, redirect or chunk-level revocation evidence. | Adapter owner: outbox/status API, recipient pinning, chunk authorization, cache lineage and bounded leases. |
| P1 | Same-host evidence rollback | HMAC chain plus retained checkpoint detects tested truncation. Shared host/key/witness may all be replaced. Manifests are not independent notarization. | Assurance: separate witness, protected signing custody, monotonic restore policy. |
| P1 | Privacy | Joined store is synthetic plaintext; original privacy stack is separate. No anonymity, complete erasure, machine unlearning, inference-resistance or unknown-backup claim. | Privacy owner: end-to-end privacy integration and copy inventory. |
| P1 | Adaptive evaluation validity | Trained tabular Q, 12-action grammar, eight steps, same task family and seed-only holdout. Sparse reward with scripted exploration. | Independent evaluator: new attack families, larger budgets, blinded oracle audit and external contributions. |
| P1 | Reasoning/reviewer persuasion | Synthetic rationales and simulated reviewers; four local-model prompts only. No trained monitor or live review assistant study. | Evaluation owner: adversarial human/model review study with consent and separate effect metrics. |
| P2 | Utility and performance | One positive workflow per arm/strategy; per-episode timings include setup and SQLite. No production load, energy or cost estimate. | Operations: workload-specific p50/p95/p99 and recovery targets. |
| P2 | Reproducibility portability | Clean standard-library demo verified locally; environment export is not a portable full-platform lock. Added CI is not yet run on GitHub. | Maintainer: multi-OS CI, pinned target-platform wheels and independent reproduction. |

## Threat coverage boundaries

Executed by the new regressions: wrong subject/tenant, caller-field spoofing, unsupported tool/schema/code/memory/stream requests, five synthetic rationale variants, fabricated citations, changed proposal, wrong role, read-to-write escalation, policy/source/recipient/consent/expiry invalidation, revoked cached release, cross-session reference use, sibling budgets, replay after process reopen, evidence-write rollback, retained-checkpoint truncation, authorized harmful source and appeal, and source-confirmation on/off/restored.

The original 841-test suite additionally exercises its existing API, disclosure, privacy, model adapters, delegation, races and fake-backend paths. Test presence is not a claim of real distributed-backend execution. Redis/Kafka/Iceberg/production-host qualification, controlled redirect packet capture, arbitrary generated code isolation, long-horizon LLM agents, independent adversarial corpus, genuine language-model RL, trained reasoning monitors, institutional reviewer studies and educational outcomes remain NOT RUN. JSON-interface rejection is not a network firewall result. Do not count missing integrations as attacks contained by the whole architecture.
