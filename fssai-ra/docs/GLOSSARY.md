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
| **Disclosure grant** | permission to see specific data for a specific purpose | signed grant bound to holder, purpose, subjects, fields, classes, basis, and expiry, checked at every read | a bearer token, a role, or consent by itself |
| **Data label** | what data is, who it concerns, and where and why it may go | classes and subjects that join by union; purposes and zones that join by intersection | a classification decided by the model |
| **Session taint** | a summary is as sensitive as what it was built from | every output is labelled with the join of everything released into its session | detection of paraphrased or inferred content |
| **Declassification** | an accountable decision to lower an output's sensitivity | a declared rule applied by the gate with an approval bound to the exact output digest, from an independent declared role | proof of de-identification or absence of re-identification risk |
| **Break-glass access** | emergency access without prior approval | self-issued, purpose- and time-bounded access that opens a review obligation and blocks further use while review is overdue | legitimacy of the emergency |
| **Sovereignty** | the institution can govern access, policy, keys, evidence, replacement and exit | deployable component interfaces plus institution-held configuration and credentials | merely running a model locally or inside national borders |
| **Delegation chain** | the sequence of hands an institutional permission passed through before it was used | an ordered, signed list of hops from a root grant to the acting principal, verified from the root down on every call | that any hop understood the task, or that the chain describes a real org structure |
| **Attenuation** | a permission may be narrowed when passed on, never widened | each hop's scope is covered by its delegator's; the chain confers the *intersection* of every grant along it | that the narrowed authority is small enough to be safe |
| **Confused deputy** | a component with broad permissions doing a narrowly-permitted component's work for it | the effective scope of work done *for* another principal is intersected with that principal's own conferred scope | protection when the actor does not disclose whose work it is — an undisclosed beneficiary is refused, not resolved |
| **Bearer authority** | a permission that works for whoever is holding it | an authority object not bound to the principal presenting it — refused here, because a chain authorises the principal it names and no other | that binding prevents theft of the principal's own credential |
| **Review assistance** | a model that helps a human reviewer decide | a declared mode — unaided, summarised, or recommended — that changes the deliberation floor a deployment is permitted to set | that the reviewer read the case rather than the summary |
| **Assistant independence** | the reviewer's helper is a second opinion, not the same opinion twice | three declared properties: a different model from the proposer, a different evidence path, and an adversarial posture | any measured error correlation; the coupling is a declared parameter, not an observation |
| **Merit failure** | a decision that is procedurally perfect and substantively wrong | right operation, current version, authentic approval, ineligible applicant — detected by no digest and excluded by no invariant | that a reading human always catches it; only that nothing else can |
| **Contract coverage** | whether a written control is actually enforced | three-way status per requirement: machine-verified by a check that is itself checked to exist, attested by a named role on a cadence, or unverified | that a verified control is *adequate*, only that it is not imaginary |
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

## Acronyms in plain language

Terms used in [`MASTER_GUIDE.md`](MASTER_GUIDE.md), procurement conversations and security
reviews. Each gives what it stands for, what it means in one sentence, and why it matters here.

### Security engineering

| Acronym | Stands for | In plain words | Why it matters here |
|---|---|---|---|
| **SLOC** | Source lines of code | lines that actually do something, not counting blanks, comments or explanations | the trusted base is measured in SLOC so "small" is a number (`fssaira assure trusted-base`) |
| **SBOM** | Software bill of materials | the ingredients list of a program: every third-party package and version it uses | a buyer's scanner checks the list for known vulnerabilities |
| **TCB** | Trusted computing base | every part that must work correctly for the safety promise to hold | the model is deliberately outside it; the gate and evidence plane are inside |
| **HSM** | Hardware security module | a tamper-resistant device that holds keys and signs without ever revealing them | notary and witness keys belong in one |
| **KMS** | Key management service | a (usually cloud) service that stores keys and performs cryptography on request | the reference implementation reaches keys through `kms_vault.py` |
| **TPM** | Trusted platform module | a chip that records what software booted, so a remote party can check it | one way to attest the enforcer's build measurement |
| **TEE** | Trusted execution environment | a hardware-isolated area where code runs protected from the host | another way to attest the enforcer |
| **ASLR** | Address space layout randomisation | the operating system shuffles memory locations so exploits cannot guess addresses | host hardening under the enforcer |
| **CFI** | Control-flow integrity | a check that a program only jumps where its code intended | host hardening; not needed for memory-safe source |
| **IAM** | Identity and access management | the system that says who someone is and what they may use | agents get no standing IAM credentials |
| **IMDS** | Instance metadata service | the cloud address (169.254.169.254) a machine asks for its own credentials | must be blocked in an agent cell, or the cell is not credential-less |
| **JIT** | Just in time | access granted at the moment it is needed and removed right after | effect tokens are minted per approved effect |
| **mTLS** | Mutual transport layer security | both ends of a network connection prove their identity with certificates | gateway-to-adapter links |
| **RBAC / ABAC** | Role- / attribute-based access control | permissions by job role / by properties of the person, data and situation | the gate intersects both with the task contract |
| **MAC / HMAC** | (Hash-based) message authentication code | a keyed checksum proving a message came from a key holder and was not altered | receipts and envelopes are MAC'd |
| **Ed25519** | an elliptic-curve signature scheme | a fast, widely reviewed way to sign data with a private key and verify with a public one | notary, witness, tree-head and time signatures |
| **CT** | Certificate Transparency | the public, Merkle-tree logs that browsers use to catch bad web certificates | the evidence plane borrows its tree hashing (RFC 9162) and witnesses |
| **STH** | Signed tree head | a signed statement "the log has N entries and this root hash" | what witnesses co-sign in `transparency.py` |
| **TOFU** | Trust on first use | accepting the first thing you see as genuine, then checking consistency after | a witness says when its first checkpoint was TOFU |
| **CAS** | Compare-and-set | "change it only if it still has the value I expect", as one indivisible step | how a fenced commit refuses a stale epoch |
| **RPO / RTO** | Recovery point / time objective | how much data you may lose, and how long you may be down, after a failure | backup and failover targets for the evidence plane |

### Standards, law and governance

| Acronym | Stands for | In plain words | Why it matters here |
|---|---|---|---|
| **OWASP** | Open Worldwide Application Security Project | a non-profit publishing practical security guidance, including the Top 10 for LLM Applications and Agentic AI threat guidance | §13 of the master guide maps its risks to controls |
| **NIST** | National Institute of Standards and Technology (US) | the US standards body; publishes the AI Risk Management Framework (AI 100-1) and its Generative AI Profile (AI 600-1) | the guide's KPIs and runbooks fill the RMF's Measure and Manage functions |
| **AI RMF** | AI Risk Management Framework | NIST's structure for AI risk: Govern, Map, Measure, Manage | organises ownership and evidence |
| **ISO/IEC 42001** | International standard for AI management systems | how an organisation runs AI responsibly, audited like ISO 27001 | policy versioning, roles and monitoring evidence |
| **ISO/IEC 27001** | International standard for information security management | the common security-management certification | the enforcer and evidence plane sit inside its scope |
| **RFC** | Request for Comments | the numbered documents that define internet standards | RFC 2119 defines MUST/SHOULD; RFC 9162 defines the Merkle tree |
| **FERPA** | Family Educational Rights and Privacy Act (US, 20 U.S.C. 1232g; 34 CFR Part 99) | who may see a student's education record, and when consent is needed | `ferpa.py` encodes its release rules, each citing its section |
| **CFR** | Code of Federal Regulations (US) | the published rules agencies make under a law | FERPA's detail is in 34 CFR Part 99 |
| **COPPA** | Children's Online Privacy Protection Act (US) | rules for collecting data from children under 13 online | relevant when a workflow reaches young children directly |
| **GDPR** | General Data Protection Regulation (EU) | EU law on personal data: lawful basis, purpose limits, rights to access and erasure | purpose-bound grants and retention map to it |
| **HIPAA** | Health Insurance Portability and Accountability Act (US) | US law protecting health information | the healthcare pack's territory |
| **PII / PHI** | Personally identifiable / protected health information | data that identifies a person / health data about them | what labels and sealed release protect |
| **DPO** | Data protection officer | the person accountable for data-protection compliance | owns policy versions and the sector table |
| **DPIA** | Data protection impact assessment | a documented check of privacy risk before a system goes live | uses the guide's evidence bundle as input |
| **RACI** | Responsible, accountable, consulted, informed | a table of who does what | the master guide's ownership table |

### Operations and measurement

| Acronym | Stands for | In plain words | Why it matters here |
|---|---|---|---|
| **SLA** | Service level agreement | a promise to someone else, often with penalties | appeal deadlines, the FERPA 45-day access window |
| **SLO** | Service level objective | an internal target you measure against | revocation cut-through, verifier cadence, channel bits per minute |
| **KPI** | Key performance indicator | a number that shows whether things are working | each KPI in the guide names the command that computes it |
| **QPS** | Queries per second | how many requests arrive each second | input to the tier choice (`fssaira scale advise`) |
| **Erlang C** | a queueing formula (after A. K. Erlang) | predicts how long work waits for a free server, here a reviewer | `fssaira assure staffing` |
| **CI** | Continuous integration | every change is built and tested automatically | the refusal registry and spec citations are checked there |
| **K8s** | Kubernetes | software that runs and isolates containers across machines | the guide's agent-cell pod and network policy |
| **OPA / Rego** | Open Policy Agent / its policy language | a separate engine that evaluates policy written as code | optional; if used it joins the trusted base |
| **CIO / CISO** | Chief information / information security officer | the executives accountable for technology and for security | sponsors of adoption |

If policy and engineering staff fill this sentence differently, the discrepancy
is the work to do before deployment.

---

**Continue:** policy leaders → [`PROCUREMENT.md`](PROCUREMENT.md) · AI engineers
→ [`PLATFORM.md`](PLATFORM.md) · educators → [`SYSTEM_LITERACY.md`](SYSTEM_LITERACY.md)
