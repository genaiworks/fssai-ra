# Responsible AI: risk, mitigation, test, result

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Continue the policy route → [`IMPACT.md`](IMPACT.md)

Ethics is not a closing slide here. Each row below names a risk, the concrete
mitigation in the code, the test that exercises it, and what that test actually
observed. Where a risk is not mitigated, the row says so — an honest gap is worth
more than a mitigation nobody has tested.

Three columns are the load-bearing ones. **Mitigation** must name a mechanism, not
an intention. **Test** must name something runnable. **Result** must be an
observation, not a claim.

Regenerate the underlying figures with `python scripts/generate_results.py`.

---

## 1. The model behaves badly

| Risk | Mitigation | Test | Result |
|---|---|---|---|
| A compromised or jailbroken model proposes harmful actions | Independent policy enforcement point evaluates the *actual* operation against an explicit grant; the model holds no credential and no execution method | `compromised_model_against_least_privilege`; the three-arm comparison | 7 of 7 attacks contained; **0** harmful actions reached the protected asset, against 28 unguarded and 8 with a prompt-plus-allowlist baseline |
| The model understates the risk of its own proposal | Action class read from the deployment's capability catalogue, never from the proposal; unknown capabilities fail closed as consequential | `tests/test_privilege_invariance.py` (7 tests); `model_declares_its_own_action_class` | Every downgrade reclassified and recorded; 0 downgraded proposals executed |
| The model hallucinates a justification | The rationale is recorded and **never** consulted for the decision; the executor checks the operation | `AA-1`; policy-decision records carry `model_rationale` alongside the independent verdict | Decisions are computed from operation and policy; the rationale appears only in evidence |
| A routing layer sends work to a more permissive path | Grant, catalogue, and enforcement point are identical on every route | `test_routing_cannot_widen_authority` | Routing changes which model answers, never what it may do |

## 2. Injected and poisoned content

| Risk | Mitigation | Test | Result |
|---|---|---|---|
| Prompt injection inside a retrieved document | Mechanical markers stripped at import; retrieved text fenced as data; **the enforcement point ignores retrieved text entirely when deciding** | `injection_specimen_stripped_at_import`; `CF-BI-02`; live run against Ollama | Markers removed; a real local model given the specimen proposed no escalating action; and the controls do not depend on that outcome |
| Injection written in ordinary language | **Not mitigated at the boundary, and not claimed to be.** Containment is downstream: default-deny egress, least privilege, and an approval bound to an exact proposal | The compromised-model arm assumes injection already succeeded | Containment holds when injection is assumed successful — which is the only assumption worth testing |
| A fence-escape attempt in a document | Fence markers at line start are neutralised before the envelope is built | `test_a_document_cannot_close_the_fence_and_start_instructing` | Exactly one real closing fence survives per block |
| Poisoned upstream data | Lineage per job plus versioned snapshots and rollback to the last approved state | `poisoned_data_rolled_back_to_approved_snapshot`; `CF-RD-01` | Approved rows restored exactly; the affected job identified by input hash |

## 3. Data protection and exfiltration

| Risk | Mitigation | Test | Result |
|---|---|---|---|
| Records sent outside the boundary | Default-deny egress classification; egress is an axis independent of impact | `test_prompt_injection_is_stripped_and_egress_blocked` | Egress denied by default; the ablation shows removal restores exfiltration |
| Exfiltration hidden in a tool argument | Argument inspection for URLs, mail addresses, and host:port on non-egress tools | `exfiltration_hidden_in_arguments` | Denied with `EGRESS_IN_ARGUMENTS`. **Limit:** a determined encoder can evade a regular expression; this is a cheap layer, not the control |
| Prompts and records leaving via the model | Ollama by default, running on institution-controlled hardware; a non-local endpoint raises an explicit sovereignty warning | `test_a_non_local_endpoint_is_reported_as_a_sovereignty_warning` | The architecture does not stop you using a hosted API; it stops you doing so silently |
| A metrics endpoint becoming a data path | Counters only — never payloads, identifiers, or record contents; the exporter is listed as an egress interface | `docs/PLATFORM.md`; interface inventory `IB-3` | Scraping exposes aggregate counts and nothing about any person |

## 4. Human oversight and accountability

| Risk | Mitigation | Test | Result |
|---|---|---|---|
| A consequential action taken with no person accountable | Approval bound to one exact proposal: target, arguments, evidence version, resource version, role, audience, expiry | 12 exact-action scenarios; 240 model-checked configurations | 0 unauthorized mutations across every denial scenario and every checked configuration |
| A person approves one thing and something else happens | Canonical proposal digest re-checked at execution | `changed_target_after_approval`, `changed_arguments_after_approval`, `changed_evidence_version_after_approval` | All denied with `APPROVAL_PAYLOAD_MISMATCH`, zero mutations |
| Approval by someone outside their remit | Approver role checked against the exact profiled transition; role taken from the authenticated principal, never the request body | `role_not_permitted_for_transition`; `test_openapi_control_plane_workflow` | Denied with `APPROVER_ROLE_NOT_ALLOWED` |
| Self-approval | Separation of duties refused at issue time | `requester_approves_own_proposal`; `CF-AA-15` | The approval is never issued |
| **Rubber-stamping: the reviewer approves without reading** | **Partially mitigated, and only at the level of the regime.** Binding an approval to an exact proposal prevents *reuse*; it cannot make a person read. What can be bounded is the condition under which reading stops being possible: a declared review capacity per window, a deliberation floor below which the approval is refused at issue rather than flagged, and mandatory escalation to a second distinct reviewer under sustained load | `tests/test_oversight.py`; `AA-8`, `AA-9`; `fssaira oversight` | On a queue at 5x declared attentive capacity, 4 structurally valid but substantively wrong actions execute without the control and **0** with it, at a reported cost of 32 deferrals to the manual fallback. **This does not make anyone read.** It refuses to accept an approval issued under conditions in which reading was not possible |
| **Whether real reviewers actually degrade this way** | **Not mitigated, and not claimed.** The degradation curve driving the trial above is a *declared parameter* an institution supplies, labelled as such in the module, the CLI output, the generated results, and the assurance ledger | — | **Open. Unmeasured. No reviewer was observed.** This is the largest gap between the oversight claim and a field claim, and closing it needs a study with human subjects rather than more code |
| **A second signature under the same institutional pressure** | **Not mitigated.** Escalation requires a *distinct* reviewer; it cannot establish that the second judgement is independent of the first | `test_sustained_load_escalates_to_a_second_distinct_reviewer` (distinctness only) | **Open.** Two signatures obtained under the same backlog, targets, and management are not two independent judgements, and nothing here shows otherwise |

## 5. The record

| Risk | Mitigation | Test | Result |
|---|---|---|---|
| An agent writes or edits its own record | Append requires a credential held only by the evidence service | `agent_cannot_write_its_own_record`; `CF-AA-01` | Refused. In the unguarded and prompt-guarded arms, by contrast, the runtime writes its own log |
| Silent alteration of a past record | Hash chain; each record's hash covers the previous | `insider_record_tampering_detected`; `CF-AA-02` | Alteration breaks verification. **Limit:** tamper-evidence detects; it does not prevent |
| Silent truncation of history | Independent Spark job recomputes hashes **and** checks for sequence gaps | `jobs/verify_evidence_chain.py` | A gap is reported as `COMPROMISED`. **Limit:** requires the archive to be running; not covered by the offline suite |
| A mutation lands with no record of who authorized it | Single transaction where the register and ledger share a database; otherwise reported uncertain, retained, and reconciled once | `tests/test_atomic_execution.py`; `outcome_evidence_interruption_and_recovery` | On the transactional profile the state is unreachable; on the best-effort profile it is detected and reconciled exactly once |
| Self-reported verification | The chain is re-verified by a different process, with different credentials, on a different schedule | `XC-3` | A monitor sharing a process with the thing it monitors proves nothing |

## 6. Availability, and the person waiting

| Risk | Mitigation | Test | Result |
|---|---|---|---|
| A runaway agent exhausts a downstream system | Call budget counted by the enforcement point, not the agent's loop | `runaway_agent_exhausts_call_budget` | Three allowed, three denied, at the policy |
| Resource-exhaustion payload at the boundary | Size and declared-envelope checks before anything is parsed | `import_rejects_oversize`, `import_rejects_size_mismatch` | Quarantined at the edge |
| **Fail-secure becoming fail-stuck** | A named manual fallback with a stated turnaround, declared in the profile and owned by a named role | `XC-4`; false-denial rate reported beside containment | **0.0 false-denial rate** across 6 benign tasks, and 100% benign completion in all three comparison arms. **Limit:** a small synthetic suite bounds over-restriction; it does not measure real usability |
| **The oversight control becoming the thing that fails her** | The deferral count is published beside the containment figure rather than netted off, with the demand-to-capacity ratio that explains it; the control is silent when the institution is staffed for the work | `test_the_cost_of_the_control_is_reported_rather_than_hidden`; `test_a_queue_inside_capacity_defers_nothing` | 32 of 39 actions deferred at 5x capacity, and 0 deferred inside capacity. **This is a real cost borne by the person waiting.** Refusing an approval preserves the boundary and delays the student; an institution that dislikes the number was already over capacity and had no instrument that said so |
| Denials nobody answers | Denial counters exposed as named metrics for the owner of the manual path | `tests/test_security_and_telemetry.py` | A denial rate nobody watches is a service failure nobody sees |

## 7. Fairness, inclusion, and the digital divide

This section is short because the evidence is thin, and saying so is the point.

| Risk | Status |
|---|---|
| The underlying eligibility policy is inequitable | **Out of scope, and named as such.** The architecture governs *who may act and on what evidence*. It cannot make an unfair rule fair, and an institution that adopts it without examining its own policy has automated the unfairness more accountably |
| The system performs worse for some groups | **Not measured.** Synthetic cases cannot establish real-world fairness. Any deployment must measure this on its own population, before expanding autonomy |
| Evidence is unusable by the person it concerns | **Partially addressed.** The evidence artifact is specified per requirement and must name what lets a person argue. Local-language rendering and accessibility are deployment obligations, untested here |
| The architecture is too heavy for a low-resource institution | **Actively mitigated.** The full suite runs offline on a laptop in under two seconds with no GPU; SQLite is a first-class durable profile, not a toy; the teaching mode has one dependency. An institution with no cloud budget can verify every claim in this repository |
| Reliance on a model nobody local can run | **Mitigated by design.** The default is a local model, the deterministic backend needs no weights at all, and every control is measured with the model assumed hostile |

## 8. Environmental cost

The deterministic evaluation, the model checker, and the conformance suite use no
GPU and complete in seconds. Inference cost is a property of whichever model an
institution chooses and is not measured here. We make **no** energy claim, in
either direction: an architecture that constrains an agent's authority does not
by itself reduce the cost of running it.

---

## What would change our mind

A method should be able to say what evidence would count against it.

- A benign suite large enough to show a material false-denial rate would mean the
  containment figures are bought with refusals after all.
- A reviewer study showing that binding approvals to exact proposals does not
  change approval quality would undermine the central control's value, even
  though the binding itself would still hold.
- A backend that passes the conformance suite while failing a real attack would
  mean the suite tests the wrong properties.

None of these has been run. They are the experiments we would want to see.
