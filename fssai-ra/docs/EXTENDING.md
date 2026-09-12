# Extending the reference architecture

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Continue the engineering route → [`ASSURANCE.md`](ASSURANCE.md)

This guide helps a university, public agency, researcher, or student adapt the
teaching profile without inheriting claims that its environment has not tested.

## Begin with one consequential action

Write one sentence in this form:

> The agent may propose **operation** for **scope**, but only **authority** may
> commit it after reviewing **evidence**, and **owner** restores service if the
> control is unavailable.

Choose a narrow, synthetic workflow before connecting records or real tools. Define
a manual service path so fail-secure automation does not become denial of service.

A worked example of everything on this page is in the repository.
[`profiles/academic_record_correction.yaml`](../profiles/academic_record_correction.yaml)
was added by following it, and it is deliberately *structurally* different from
the reference profile — a multi-role chain, a rejection an appeal can reopen,
five transitions over six statuses — because a method that only works on the
shape it was designed against has not been shown to generalise.

Read what it cost us before you start. Its first bounded model check **failed**,
and the defect was in the library rather than the new profile: a declared
`approval_role` on a non-consequential transition was silently unenforced. That
is the normal experience of adding a second domain, and it is the argument for
adding one. See [`tests/test_generalization.py`](../tests/test_generalization.py).

Copy `profiles/template.yaml`, replace its domain language, and enumerate only the
state transitions that the executor may perform. Validate it before writing code:

```bash
fssaira validate-profile profiles/your_profile.yaml
```

The profile is an executable allowlist, not descriptive metadata. An approved
transition outside it is denied independently by the executor.

## Add a complete control-contract entry

Add YAML under `contract/` with these fields:

```yaml
id: DOMAIN-UNIQUE-ID
protected_asset: What can be harmed or disclosed
permitted_operation: The narrow action and scope the agent may request
enforcement_point: The independent component that makes the decision effective
owner: The role accountable for policy and recovery
test: The attempt and concrete side effect to observe
evidence_artifact: What a reviewer can later reconstruct
failure_response: How automation stops and service continues
```

The enforcement point must inspect the actual operation, target, arguments, current
state, and identity. A model-generated explanation is recorded context, not an
authorization source.

## Write the failure test first

For every consequential capability, test at least:

- altered target or arguments after approval;
- expired, revoked, wrong-audience, or reused approval;
- stale authoritative record after review;
- direct backend access using the agent identity;
- evidence-service and policy-service unavailability;
- retry before and after a simulated commit;
- one legitimate task, to measure false denial and operational burden.

Assert the real side effect, not only a policy function's return value. Count writes,
inspect controlled sinks, reconstruct the evidence bundle, and disclose the test
boundary and denominator.

Run the reusable exact-action scenarios and retain the JSON result with the commit:

```bash
fssaira evaluate profiles/your_profile.yaml --output evaluation-report.json
```

The built-in runner checks one profile transition. Domain-specific extensions must
add misuse, equity, appeal, accessibility, and benign-task cases relevant to the
people and decisions involved; eight generic scenarios are a floor, not coverage.

## Replace teaching components deliberately

Keep the interfaces and observable invariants while replacing in-memory stores:

- use an institutional identity and signing service instead of the public HMAC key;
- make idempotency records durable and transactional with the target system;
- back `PendingOutcomeStore` with a durable outbox committed atomically with the
  authoritative mutation;
- checkpoint evidence independently and monitor missing sequence numbers;
- test crash points before commit, after commit, and during reconciliation;
- preserve a staffed manual path with a named owner and service-level objective.

The repository already supplies reference implementations for the first engineering
step: `RedisCaseRegister`, `RedisApprovalUseStore`, `RedisPendingOutcomeStore`,
`RedisEvidenceLedger`, `KafkaEventPublisher`, the FastAPI control plane, and the
Kafka-to-Iceberg Spark job. Extend their interfaces or replace them; do not bypass
the invariants they enforce. Run `scripts/smoke_stack.py` after every backend change.

## Preserve profile labels

- **Teaching profile:** synthetic data, in-memory services, shared-host limitations.
- **Institutional pilot:** separately administered identities, networks, keys,
  evidence custody, restoration, human continuity, and domain review.
- **Hardware-isolated profile:** a physical topology and interface inventory, tested
  directional gateway, maintenance procedure, and all institutional controls.

Passing one profile never implies assurance for another. A hardware diode constrains
one link; it does not validate imported text or close output, maintenance, telemetry,
or operator paths.

## Submit an extension

Open an issue describing the workflow, protected people and records, threat model,
manual fallback, and intended profile. A pull request should include the contract
entry, implementation, attack test, benign test, ablation where meaningful, evidence
example, and limitations. Use synthetic or properly licensed data only. Never include
credentials, private model artifacts, or identifiable student records.


## Declare what review you can actually supply

A profile says which transitions are consequential. It does not say how many of
them your institution can genuinely review in a day, and a boundary that routes
every consequential action to a named human is only a control while that human is
still deciding.

```bash
fssaira oversight profiles/your_profile.yaml --reviewers 11 --deliberation-floor 45
```

State three numbers you are willing to defend: the approvals one reviewer may
issue per window, the minimum time a proposal needs to be read, and the hours a
reviewer is actually available for this queue. The tool turns them into a ceiling
and tests whether the control binds at it.

If demand exceeds the ceiling, the deferral count is the answer, not a parameter
to loosen. Publish the ceiling before the automation roadmap.

## Contribute the attack we did not think of

Every attack in this repository was written by the people who built the defence.
If your domain has a failure mode ours does not, it belongs in
[`challenges/`](../challenges/) — seven fields of YAML, no student record, no
deployment detail, no contributor code. It is scored against three architectures
and attributed to you.

That is the cheapest possible way to make someone else's assurance argument
better, and it is the only kind of evidence this project cannot take credit for.
