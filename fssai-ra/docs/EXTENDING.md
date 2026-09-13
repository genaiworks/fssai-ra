# Extending the reference architecture

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Continue the engineering route → [`ASSURANCE.md`](ASSURANCE.md)

This guide helps a corporation, healthcare organization, university, public
agency, researcher, or community organization adapt the security kernel without
inheriting claims that its environment has not tested. See the shipped matrix in
[`DOMAIN_PACKS.md`](DOMAIN_PACKS.md) and inventory it with `fssaira profiles`.

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

Two additional packs exercise regulated-data shapes outside education:
[`corporate_confidential_data.yaml`](../profiles/corporate_confidential_data.yaml)
and [`healthcare_record_access.yaml`](../profiles/healthcare_record_access.yaml).
They declare purpose, data classes, prohibited uses, applicable obligations, and
separate data/privacy/security owners. They are executable teaching examples,
not compliance claims.

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
`RedisEvidenceLedger`, `KafkaEventPublisher`/`KafkaEventConsumer`,
`IcebergSnapshotStore`, the FastAPI control plane, and the idempotent
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

## Bind every contract entry to something that runs

A contract entry has seven fields and one of them is a failure test. Writing the
sentence is not the same as having the test, and nothing used to notice the
difference:

```bash
fssaira coverage --dir contract
```

Every requirement must end up in one of two places. Either an executable check is
**bound** to it in `contract/bindings/`, naming the mechanism and a locator that
is itself checked to exist — or the contract entry declares
`verified_by: organizational` with an `attested_by` role and an
`attestation_cadence`, for the controls no program can prove: key custody, a
signed interface inventory, a manual fallback a real person will staff.

Anything else is reported as **unverified**, and that number is printed rather
than buried. Ours was 18 of 28 the first time we measured it. The bindings file
is deliberately separate from the contract because the contract is your
institution's document and the bindings are your implementation's claim about it;
replace the implementation and you rewrite only the second.

## Say what happens when your agent asks another agent

If your workflow has one agent calling one tool, skip this. If it calls a tool
server, a plugin, a sub-agent, or anything your team did not write, authority
composes and the single-agent controls do not cover the composition:

```bash
fssaira delegation --max-depth 3
```

Declare two things. **How deep** delegation may go — an accountability bound
rather than a security one, because past some length nobody can answer who
decided. And **whether a machine may pass on consequential authority at all**;
the default is no, because a named human approved *this* agent acting, not an
open-ended population of its successors.

Then check the property that per-hop validation cannot give you: a chain confers
the *intersection* of every grant along it, recomputed from your institutional
root grant, and it authorises the principal presenting it and no other.

## Declare the independence of anything that reviews your model's work

If reviewers in your deployment get a model assistant — and at scale they will —
the deliberation floor you set is only defensible in proportion to how
independent that assistant is of the model writing the proposals:

```bash
fssaira assisted-review profiles/your_profile.yaml --lowered-floor 10
```

Three declarations, all contractible: a different model from the proposer, an
evidence path that is not the proposer's assembled packet, and an adversarial
posture. Declare fewer and the gate refuses the lowered floor at startup rather
than letting the deployment run with an oversight control that has quietly become
a formality.

This is an attestation, not a verification. Nothing here inspects which model you
actually call, and the correlation between a proposer and a dependent assistant
is a declared parameter — ours, until someone measures it on real systems.

## Contribute the attack we did not think of

Every attack in this repository was written by the people who built the defence.
If your domain has a failure mode ours does not, it belongs in
[`challenges/`](../challenges/) — seven fields of YAML, no student record, no
deployment detail, no contributor code. It is scored against three architectures
and attributed to you.

That is the cheapest possible way to make someone else's assurance argument
better, and it is the only kind of evidence this project cannot take credit for.
