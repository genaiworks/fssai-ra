# Shared glossary for policy leaders and AI engineers

> **Documentation navigation:** [Documentation map](README.md) ·
> [Start the guided tour](START_HERE.md) · [Policy route](README.md#policy-leader-route) ·
> [Engineering route](README.md#ai-engineer-route)

The same word often means different things in governance and software. This
glossary makes the translation explicit.

| Term | Plain policy meaning | Engineering meaning here | What it does **not** establish |
|---|---|---|---|
| **Agent** | software allowed to pursue a bounded task | a proposal-producing model runtime with a scoped identity and tools | a legal or accountable person |
| **Authority** | legitimate power to affect a person or institutional record | an authenticated capability to perform an exact operation on a target | model confidence or persuasive language |
| **Proposal** | a recommendation awaiting valid disposition | a canonical structured action with requester, target, arguments, evidence and version | permission to execute |
| **Consequential action** | an action that can materially affect rights, access, records, resources, or obligations | an operation/transition the profile maps to independent human approval | every model response or routine read |
| **Control contract** | the institution’s enforceable promise for one capability | seven required fields joining property, asset, operation, enforcement, owner, test, evidence and response | certification or complete risk coverage |
| **Enforcement point** | the place where a rule can actually stop an outcome | code or infrastructure independent of the model that denies a request before mutation | a prompt telling the model to behave |
| **Capability** | a specifically delegated institutional power | an identity-bound operation and resource scope | broad job title or system access |
| **Least privilege** | give only the power needed for the assigned task | narrow agent identity, tool allowlist, operation, target and field scope | safety if the allowed tool itself is overpowered |
| **Exact-action approval** | a person approves this action, not a general intention | authenticated approval bound to the proposal digest, reviewer role, audience and expiry | proof that the reviewer understood the case |
| **Oversight ceiling** | the maximum consequential workload the declared reviewers can genuinely cover | capacity computed from roster, time, quota and deliberation-floor assumptions | observed reviewer accuracy or fatigue |
| **Manual fallback** | the named human service route when automation stops | a profile-declared recovery response outside automatic execution | an undocumented bypass around controls |
| **Evidence record** | a reconstructable account of what was proposed, authorised and done | hash-chained intent/outcome entries with controlled write access | truth, fairness, completeness, or independent custody by itself |
| **Decision packet** | the records needed to inspect one decision | exported proposal, approval, receipt and selected evidence records | the full ledger or proof that source evidence was true |
| **Tamper-evidence** | evidence that retained records no longer agree | digest/signature/chain mismatch detected by a verifier | prevention of tampering or proof of justice |
| **Independent verifier** | a checker not relying on the agent’s own claim | separate code/process that recomputes defined properties | independence from a shared host administrator unless deployed that way |
| **Bounded verification** | exhaustive checking inside a declared finite scope | enumeration of profile operations, transitions, identities, approvals and versions against invariants | proof for unbounded inputs or infrastructure behaviour |
| **Ablation** | evidence that a claimed safeguard actually mattered | remove one control and check whether the specified harm returns | evidence against harms absent from the experiment |
| **Conformance** | a replacement still satisfies the required duties | shared behavioural checks run against memory, SQL, or adopter adapters | production qualification of the backend |
| **Sovereignty** | the institution can govern access, policy, keys, evidence, replacement and exit | deployable component interfaces plus institution-held configuration and credentials | merely running a model locally or inside national borders |
| **One-way data diode** | a physically enforced inward-only connection | hardware that can replace the repository’s no-read-back software transport seam | control of every other egress, administrator, media, radio, power or side-channel path |
| **Snapshot** | the exact version of data relied on for a decision | immutable/versioned reference plus retained content and manifest | preservation if referenced bytes are later deleted |
| **Replay safety** | retrying must not perform the action twice | request and proposal identity, atomic approval use, receipt replay and reconciliation | safe retry when an external system lacks idempotency or status query |
| **Fixture observation** | a result seen in the published synthetic experiment | deterministic output under a named profile, source hash and environment | a probability, production result, certification, or universal guarantee |
| **Digital public good** | openly reusable public-interest infrastructure or knowledge | Apache-2.0 code, profiles, tests, worksheets and shareable failure cases | automatic institutional readiness or equitable adoption |

## One sentence both roles should be able to complete

> For **[exact operation]** on **[protected asset]**, the agent may **[bounded
> proposal capability]**; only **[authorised role/service]** may execute it at
> **[independent enforcement point]**; failure is demonstrated by **[test]**,
> recorded as **[evidence]**, and recovered by **[named owner and route]**.

If policy and engineering staff fill this sentence differently, the discrepancy
is the work to do before deployment.

---

**Continue:** policy leaders → [`PROCUREMENT.md`](PROCUREMENT.md) · AI engineers
→ [`PLATFORM.md`](PLATFORM.md) · educators → [`SYSTEM_LITERACY.md`](SYSTEM_LITERACY.md)
