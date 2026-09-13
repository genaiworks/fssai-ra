# Trust by Construction: a pattern language for AI systems over sensitive data

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Choose a blueprint below, then build its first pack with [`EXTENDING.md`](EXTENDING.md) and measure it with `make reviewer`.

## Purpose

This document turns the repository into a reusable design discipline. It is meant
for architects, engineers, security and privacy leaders, auditors, and policy
owners who will build AI systems that read sensitive data, recommend or take
consequential actions, delegate work between agents, or operate tools.

It applies equally to a corporate knowledge copilot, a clinical-record assistant,
a research data enclave, a public-benefits caseworker agent, and a university
registry. Education is one worked context in this repository. It is not the
boundary of the pattern.

Every pattern below names the mechanism that implements it in this repository and
the command or test that shows it binding. A pattern with no executable check is
labelled as organizational. That discipline is itself the first lesson: **a
control that exists in review and not at runtime is the failure this whole
language exists to eliminate.**

## The constitution: two rules

> **1. A model may propose an action. It cannot manufacture the authority to
> execute it.**
>
> **2. A model may request information. It cannot manufacture the entitlement to
> see it, and it cannot launder what it saw.**

Everything else derives from these two rules and from one engineering
consequence: **neither rule can be enforced inside the model.** A prompt can ask a
model to behave. Only a component the model cannot reach can make the rule true.

## Seven laws that follow

1. **Separate the proposer from the authority.** The component that reasons holds
   no write credential and no record-store credential.
2. **Bind approval to the exact thing approved.** An approval covers one digest:
   one action, one resource version, or one output.
3. **Authority only narrows; restriction only accumulates.** Delegation attenuates
   along a chain. Labels tighten along a data flow. Neither can widen at any hop.
4. **Check at the moment of use, against live state.** Policy, resource version,
   consent, revocation, and endpoint location are evaluated when the effect
   happens, not when a token was minted.
5. **Human attention is a finite, declared resource.** Oversight that exceeds
   capacity is not oversight, so load must be controlled and excess must defer.
6. **Remember independently, without making a second copy.** Evidence lives outside
   the model's control, records intent before effect, and holds digests rather
   than protected content.
7. **Fail secure to a named human route.** Uncertainty stops automation and hands
   the case to a staffed fallback with an owner.

## Pattern catalogue

Each entry gives the problem, the solution, where this repository implements it,
and how to see it bind.

### Authority patterns

**A1 Proposal Is Not Authority**
- *Problem:* A capable model is given a tool that changes records, and its output
  becomes the change.
- *Solution:* The model emits a structured proposal. An independent executor with
  the only write credential decides.
- *Here:* `exact_action.AccountableExecutor`, `control_plane.py`.
- *Verify:* `fssaira verify profiles/student_support.yaml`; `tests/test_privilege_invariance.py`.

**A2 Exact-Action Approval**
- *Problem:* A human approves an intention and a different action executes.
- *Solution:* Approval signs the proposal digest, resource version, role, audience,
  and expiry. Any change voids it.
- *Here:* `ApprovalAuthority`, model-check approval variants.
- *Verify:* `fssaira evaluate`, scenario `changed_target_after_approval`.

**A3 Capability Catalogue Over Self-Declaration**
- *Problem:* The model labels its own action low risk to skip review.
- *Solution:* The action class comes from an institution-owned catalogue. Unknown
  capabilities are consequential by default.
- *Here:* `bounded_intelligence.py`.
- *Verify:* scenario `model_declares_its_own_action_class`.

**A4 Attenuating Delegation**
- *Problem:* Authority accumulates across agent hops that are each individually
  reasonable.
- *Solution:* Every chain is rooted in an institutional grant, verified whole, bound
  to its bearer, and may only narrow.
- *Here:* `delegation.py`.
- *Verify:* `fssaira delegation`.

**A5 Bounded Oversight Capacity**
- *Problem:* Approval queues exceed what reviewers can genuinely examine, and
  rubber-stamping follows.
- *Solution:* Declare roster, quota, and deliberation floor. Enforce them, and defer
  excess to a manual route.
- *Here:* `oversight.py`.
- *Verify:* `fssaira oversight profiles/student_support.yaml --sweep`.

**A6 Independent Review Assistant**
- *Problem:* A review assistant built on the proposer's model repeats its errors
  while every control stays green.
- *Solution:* A lowered deliberation floor is accepted only for declared model,
  evidence-path, and adversarial independence.
- *Here:* `assisted_review.py`.
- *Verify:* `fssaira assisted-review profiles/student_support.yaml`.

**A7 Idempotent, Reconciling Execution**
- *Problem:* Retries duplicate effects. Crashes leave false success or blind replays.
- *Solution:* Persistent request identity, first-writer binding, intent before
  effect, and reconciliation of uncertain outcomes exactly once.
- *Here:* `atomic_execution.py`, `resilience.py`.
- *Verify:* `fssaira race-test`, `fssaira resilience`.

### Data patterns

**D1 Purpose-Bound Grant**
- *Problem:* Role-based access permits the same role for treatment, research,
  marketing, and training.
- *Solution:* A signed grant names holder, purpose, subjects, fields, classes, basis,
  and expiry. It is not a bearer token and cannot be self-issued.
- *Here:* `disclosure.DisclosureGrant`, `GrantAuthority`.
- *Verify:* `fssaira disclosure PACK`, flows `purpose_switch_on_valid_grant` and `borrowed_grant_confused_deputy`.

**D2 Context Gate**
- *Problem:* A retrieval service with a broad read credential decides what a model
  sees.
- *Solution:* The gate alone holds the record-store credential. It releases the
  intersection of grant, request, live consent, and endpoint zone. There is no
  "all fields" request.
- *Here:* `DisclosureGate.assemble_context`.
- *Verify:* DX-1 in the disclosure bounded model check.

**D3 Sticky Session Label**
- *Problem:* A summary of restricted data leaves as unlabelled text.
- *Solution:* Every output carries the join of everything released into its
  session. The model's claimed label is recorded and ignored.
- *Here:* `DisclosureGate.derive_output`, `DataLabel.join`.
- *Verify:* flow `summary_laundering_with_self_label`; DX-4.

**D4 Exact-Output Declassification**
- *Problem:* De-identification or aggregation becomes a way to launder anything.
- *Solution:* Only a declared rule lowers a label, with an approval bound to the
  output digest, from the declared role, by someone other than the holder. The gate
  applies the transform.
- *Here:* `DisclosureGate.declassify`.
- *Verify:* the four `declassify_*` flows.

**D5 Consent and Revocation as Live State**
- *Problem:* A grant minted before consent was withdrawn is still honoured.
- *Solution:* Consent and revocation are queried at every read, never copied into
  tokens.
- *Here:* `ConsentRegister`, `DisclosureGate.revoke_grant`.
- *Verify:* `tests/test_disclosure.py::test_consent_withdrawal_and_revocation_take_effect_at_next_read`.

**D6 Residency-Aware Model Routing**
- *Problem:* Restricted data is sent to whichever model endpoint is configured,
  including external APIs.
- *Solution:* Every endpoint resolves to a declared zone. Every class declares its
  permitted zones. Undeclared endpoints receive nothing.
- *Here:* `disclosure.model_endpoints` and `class_zones`.
- *Verify:* flow `restricted_data_to_disallowed_endpoint`.

**D7 Break-Glass With Debt**
- *Problem:* Emergency access is either impossible, which endangers people, or
  unlimited, which conceals abuse.
- *Solution:* Allow self-issued emergency access for declared purposes, bounded in
  time, with a justification. Each use opens a review obligation. Unreviewed debt
  blocks further use.
- *Here:* `break_glass` policy; the healthcare pack's review transitions.
- *Verify:* `break_glass_*` flows; DX-5.

**D8 Evidence Without Content**
- *Problem:* The audit log becomes a second, less protected copy of the data.
- *Solution:* Record field names, subjects, codes, and digests. Write intent before
  deciding, and release nothing when evidence is unavailable.
- *Here:* `DisclosureGate._guarded`, `evidence.py`.
- *Verify:* DX-2 and DX-6.

**D9 One-Way Import Boundary**
- *Problem:* Untrusted content arrives with instructions, or opens a return path.
- *Solution:* Signed, schema-checked, quarantining import with no read-back route;
  a certified diode where the threat model requires hardware.
- *Here:* `import_boundary.py`, `diode_transport.py`.
- *Verify:* `fssaira evaluate`, import-boundary scenarios; `docs/DIODE_DEPLOYMENT.md`.

### Assurance patterns

**S1 Reference Predicate Model Check**
- *Problem:* A hand-written test suite only covers the attacks its authors imagined.
- *Solution:* Enumerate the declared state space, run the real code for each point,
  and compare with a predicate written independently of the implementation.
- *Here:* `verification.py`, `verify_delegation_space`, `verify_disclosure_space`.

**S2 Ablation as Proof of Necessity**
- *Problem:* A control is claimed to matter without evidence.
- *Solution:* Remove each control in turn. It is load-bearing only if a named harm
  returns.
- *Here:* evaluation, delegation, and disclosure ablations.

**S3 Three-Architecture Comparison**
- *Problem:* Results without a baseline cannot show what the design adds.
- *Solution:* Run the same flows against an unguarded design, a conscientious
  conventional design, and this architecture.

**S4 Contract Coverage**
- *Problem:* A written control is bound to no test.
- *Solution:* Every contract requirement is machine-verified by a bound check that
  exists, or attested by a named role on a cadence. Unverified is the number to
  watch.
- *Here:* `coverage.py`. *Verify:* `fssaira coverage`.

**S5 Conformance for Replacement**
- *Problem:* Swapping a backend silently drops a guarantee.
- *Solution:* Portable behavioural checks run against every backend profile.
- *Here:* `conformance.py`. *Verify:* `fssaira conformance --backend sql`.

**S6 Declared, Not Observed**
- *Problem:* Assumptions are reported as measurements.
- *Solution:* Every parameter and result says whether it was declared, computed on
  fixtures, or observed in the field. Open evidence stays open.
- *Here:* `GAPS.md`, `fssaira doctor`, the `limits` in every generated report.

**S7 Evidence Is Regenerated, Never Inherited**
- *Problem:* A new deployment quotes another deployment's results.
- *Solution:* The scaffold starts with empty assurance, and every pack reports its
  own denominators.
- *Here:* `fssaira init`, `fssaira profiles --verify`.

## Anti-patterns

| Anti-pattern | Why it fails | Replace with |
|---|---|---|
| **Prompt as policy** | a model can be persuaded, injected, or simply wrong | A1, D2 |
| **Model self-classification** | the component under control sets its own level of control | A3, D3 |
| **Service-account retrieval** | whoever reaches the retriever inherits all of its access | D1, D2 |
| **Bearer grants** | a grant nobody is bound to can be borrowed by any agent | D1, A4 |
| **Consent snapshot** | yesterday's permission overrides today's withdrawal | D5 |
| **Approve the intention** | the executed action differs from the reviewed one | A2 |
| **Unlimited human-in-the-loop** | review capacity is exceeded and approval becomes a ritual | A5 |
| **Log as second copy** | the audit trail leaks what the controls protected | D8 |
| **Dependent second opinion** | the assistant shares the proposer's blind spots | A6 |
| **Borrowed evidence** | results from another domain or deployment are quoted as your own | S7 |
| **Unreachable control** | a review state or role exists in configuration that no path can reach | S1, reachability tests |

## Blueprints

Each blueprint composes patterns into a system shape. None is a product
specification. Each must be built as a domain pack with its own evidence.

### Enterprise knowledge copilot over confidential data

- **Governed object:** answers and drafts built from contracts, forecasts, customer
  records, and roadmaps.
- **Patterns:** D1, D2, D3, D4, D6, D8, A3, S4.
- **Shape:** a retrieval proxy holds all store credentials and tags every chunk
  with class and subject. A model gateway resolves endpoints to zones. A response
  gateway tracks session labels and enforces recipients. External release requires
  an aggregation rule approved by the data protection officer.
- **Start from:** [`../profiles/corporate_confidential_data.yaml`](../profiles/corporate_confidential_data.yaml).

### Clinical record assistant

- **Governed object:** access to, and summaries of, patient records. It is not
  diagnosis, treatment, triage, or prescribing.
- **Patterns:** D1, D2, D3, D5, D6, D7, D8, A2, A5.
- **Shape:** grants map to treatment relationships and research approvals. Consent
  is queried live. Break-glass is allowed with bounded debt and an enforced review
  transition. The patient portal receives only the patient's own records.
- **Start from:** [`../profiles/healthcare_record_access.yaml`](../profiles/healthcare_record_access.yaml).

### Agentic workflow automation across departments

- **Governed object:** consequential state changes proposed by orchestrated agents.
- **Patterns:** A1, A2, A4, A5, A6, A7, S1, S2.
- **Shape:** an orchestrator holds a rooted grant. Sub-agents receive attenuated
  delegations. Every effect goes through an independent executor with exact-action
  approval and load-controlled review.
- **Start from:** [`../profiles/academic_record_correction.yaml`](../profiles/academic_record_correction.yaml) and `fssaira delegation`.

### Research data enclave with AI analysis

- **Governed object:** analysis outputs over a restricted cohort.
- **Patterns:** D1, D2, D3, D4, D6, D8, D9, S6.
- **Shape:** data enters through a one-way import boundary. Analysis runs on an
  in-enclave model endpoint. Nothing leaves except through exact-output
  declassification approved by the research review authority.
- **Start from:** the healthcare pack's `deidentify_for_research` rule.

## Maturity levels

Use these levels to describe a system honestly. Each level includes the one before.

| Level | Name | A system at this level can show |
|---|---|---|
| 0 | Model-centred | prompts and model choice; no enforcement outside the model |
| 1 | Access-controlled | authenticated identities, role checks, logs |
| 2 | Authority-bound | A1–A3: proposals, exact-action approval, catalogue-owned action classes |
| 3 | Disclosure-governed | D1–D8: purpose-bound grants, context gate, session labels, declassification, live consent |
| 4 | Composition-safe | A4–A7: attenuating delegation, bounded oversight, independent assistance, reconciliation |
| 5 | Evidenced | S1–S7 regenerated for the actual deployment, plus operational drills and independent assessment |

Level 5 is not certification. It means the claims have evidence attached at the
level recorded in the evidence ladder of [`REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md).

## Design review checklist

Answer each question with a mechanism and a test, not a policy sentence.

1. Which component holds the write credential, and can the model reach it?
2. Which component holds the record-store credential, and can the model reach it?
3. Is every approval bound to an exact digest?
4. Is every data grant bound to holder, purpose, subjects, fields, classes, and time?
5. Are consent and revocation checked at the moment of use?
6. Where may each data class be processed, and what happens at an undeclared endpoint?
7. Who labels model outputs, and can the model lower that label?
8. Who may declassify, for which exact output, and can the holder do it?
9. How is emergency access bounded, and who must review it?
10. Can any agent chain end with more authority than its root?
11. How many consequential reviews can the roster genuinely supply, and what defers?
12. Does the evidence log contain the protected data?
13. Which contract requirements are unverified today?
14. Which results were regenerated in this deployment, and which are inherited?

If any answer is "the model is instructed to", the system is at level 0 for that
question.
