# Testing agent authorization at the execution boundary

Technical handout accompanying the AI Engineer and AI Con proposals. This is a reference-implementation report, not a claim of peer review or a production security certification.

The companion [technical pipeline walkthrough](TECHNICAL_PIPELINE_WALKTHROUGH.md)
extends the guard analysis into a concrete Kafka, Spark, Iceberg, PostgreSQL and
Redis data path. It is the implementation appendix for the conference papers:
the guard protects authority and disclosure decisions, while the pipeline
details transport integrity, encryption, replay, snapshots and verification.

## Question and contribution

Can a tool dispatcher contain selected unauthorized actions and disclosures after an agent chooses hostile requests? The artifact combines delegated authority, exact-action approval, and disclosure labels with an evaluation method: observe the harmful effect, remove a control, restore it, and verify that the attacker can succeed in a deliberately weakened system.

The contribution is executable failure analysis and integration guidance. Capability attenuation, reference monitors, and information-flow labels are established ideas. [Macaroons (Birgisson et al., NDSS 2014)](https://research.google/pubs/macaroons-cookies-with-contextual-caveats-for-decentralized-authorization-in-the-cloud/) provides prior art for attenuating delegated authorization. This implementation is not an implementation or empirical comparison of that protocol. [Spotlighting (Hines et al., 2024)](https://www.microsoft.com/en-us/research/publication/defending-against-indirect-prompt-injection-attacks-with-spotlighting/) studies distinguishing untrusted input within model prompts; the present fixtures instead test enforcement after a hostile action has been selected. These approaches address different boundaries and can be complementary.

## Reference request and trust-boundary contract

The proposals use one request shape so the technical story is testable:

```json
{
  "request_id": "deploy-2026-0042",
  "principal": "coordinator",
  "tool": "trigger_deploy",
  "resource": "svc-payments",
  "arguments": {"service": "svc-payments", "build": "v42"},
  "context_handle": "issued-by-dispatcher",
  "approval": "ed25519-envelope-or-null"
}
```

The model can propose the tool and arguments, but it cannot select the
principal, authority scope, signing key, callback credential or recipient
clearance. The dispatcher resolves those values from authenticated server-side
state. The approval envelope binds `request_id`, effective principal, tool,
resource, audience, expiry and the digest of canonicalized, signature-bound
arguments. The callback receives a narrow server-owned capability rather than
the approval key. This is the minimum separation needed for the examples to
mean anything beyond a decorator test.

For deployment, place the dispatcher and approval service in a separate trust
zone from model workers. Keep credentials and the target-side idempotency store
out of the worker process. A target write should accept `request_id` as an
idempotency key and return a durable receipt; if the dispatcher crashes between
the write and receipt persistence, a reconciliation query must determine the
outcome before retrying. The in-process cache in this artifact intentionally
does not make arbitrary external effects exactly-once.

## Concrete information-flow contract

The disclosure path is independent of the authority path. A trusted source
returns a value plus a data-class label; the label is attached before the source
callback executes and is unioned into every consumer session. A summary cannot
lower its own label by calling itself “public.” At release, the gate checks:

```text
session_label ⊆ recipient_clearance
AND requested_purpose ∈ recipient_allowed_purposes
AND source_grants_are_still_current
```

The effect oracle observes the outbound sink separately from the gate's error
code. This catches the exception-path defect where a tool writes a value and
then raises a refusal. Direct network access, uninstrumented logs, and
undeclared `reads` metadata remain outside this reference layer and are
explicit deployment responsibilities.

## Threat model and trusted components

The adversary chooses tool calls, arguments, requests, and output text. The dispatcher, configured tool definitions, credential holders, policy loader, approval issuer, and label propagation are trusted. Actors and sensitive records in the recorded runs are synthetic. No empirical claim is made about the probability that a real model follows an injection.

`Guard` is an in-process reference integration, not a sandbox. An attacker with arbitrary Python execution in its process can access keys, call original functions, or alter policy. A deployment must authenticate the caller, resolve its context server-side, and keep the guard and tool credentials outside agent control. A valid context handle does not by itself authenticate a network caller. `root`, `spawn`, `approve`, and tool registration are trusted control-plane operations; agents must not receive arbitrary access to them.

Delegation hops in this artifact use HMAC authentication, with a fresh secret per guard instance. This is not a distributed per-principal public-key infrastructure. Human approvals use Ed25519, but the demo approval method accepts supplied identity and role: production identity verification and a separate approval service remain integration work.

## Evaluation design

Three authored delegation arms receive the same ten hostile chains and one benign two-hop chain. The middle arm checks scope attenuation and hop authentication; it deliberately lacks other constraints enforced by the full verifier. It is not a representative benchmark of RBAC, OAuth, MCP, or any commercial agent framework. One benign case is a liveness check, not a measurement of realistic false denials.

The broader harness observes model inputs, released data, and register mutations. These effect oracles are outside the mediators, but the fixtures, attack grammar, and expected properties share authorship. Some ablations use adapters that simulate a missing check; they are interventions in a reference world rather than literal removal from a deployed service. Review adapter fidelity before interpreting causality.

## Recorded results and their denominators

| Measurement | devtools | healthcare / finance / government | Interpretation |
|---|---|---|---|
| Falsifiers held | 25/25 | 25/25 each | Fixed attack cases, not an estimated security probability |
| Ablation configurations with harm | 25/29 | 25/29 each | 27 single removals plus 2 joint removals |
| Hostile delegation chains blocked | 0 / 2 / 10 | 0 / 2 / 10 each | Three specified authored implementations |
| Benign delegation chain | Completes in all arms | Same | One positive workflow |
| Seeded red-team violations | 0/300 | 0/300 each | Sampled grammar, not independent field attacks |
| Without execution mediator | 105/300 | 103/300 each | Positive control confirms reachable harm |

The four single removals that do not expose harm involve two redundant pairs: residency/model attestation and proposal digest binding/approval single use. Joint removals expose harm. Thus 23 single removals and two paired removals yield the 25 harmful configurations. A zero-effect removal alone does not establish that a control is useless.

The four worlds reuse the cases and kernel. They demonstrate parameterization, not independent validation in four industries. The checked-in JSON files and their regeneration tests are the authoritative source for these figures.

## Integration findings from the review

The original 203-test suite passed. New wrapper-focused regressions reproduced flaws that the world harness did not cover:

- Modified contexts could widen root scope or erase a label by changing the session. The guard now registers issued contexts and rejects altered or foreign contexts at authorization and label access; spawning also validates the parent handle.
- Cached results bypassed approval validation. Replays now validate signature, audience, payload, role, and expiry before returning cached data.
- JSON coercion let a tuple reuse approval for a list, and arbitrary objects were reduced to strings. Arguments now accept strict JSON types with finite numbers and string keys, use a full SHA-256 digest, and are copied before callback execution.
- High-impact tool registration could omit an approver role. Such registrations now fail.
- The wrapper inherited the fixture's publicly known delegation secret. Each guard now generates its own secret.
- Labels were attached after callback return. Declared read labels are now attached before invocation, including callbacks that raise; read iterables are materialized at registration.

These changes strengthen the wrapper, but do not turn it into a security boundary against arbitrary code in the same process.

## Execution and disclosure limits

Successful callback results are cached in memory. A 32-caller regression checks that one guard instance runs one callback for concurrent replay. This does not provide durable exactly-once external effects. A callback may change an external system and then fail before its receipt is stored; retries fail closed and require reconciliation. Process restarts lose in-memory state. Real deployment requires an idempotency key honored by the target service, persistent receipts, and an explicit recovery protocol.

`reads` is trusted metadata; `consume` must be called on every data handoff. `release` checks a label and returns text; it is not a network proxy. Direct network access, uninstrumented logs, missing labels, and reused clean sessions can bypass the intended disclosure architecture. `Guard.from_pack` imports the release policy and depth bound, not every world-harness control. Read-grant revocation at write time and signed evidence checkpoints demonstrated in the full world must not be attributed to the guard decorator alone.

## Reproduce

From `security_systems`, use Python 3.10+ in an isolated environment:

```bash
python -m pip install -e '.[dev]'
python -m pytest
python -m ruff check src tests demo.py examples
python demo.py --no-color
python examples/guarded_agent_loop.py
trustkernel matrix
```

The suite regenerates all four evidence files in temporary paths and checks exact equality. Dependency ranges are not a reproducible lockfile; record the environment with a release. No live-model or production service evaluation was performed in this review.

## Stronger future evidence

The community extension now supplies a 36-case authored benign grid and a descriptive local warm-read timing experiment in `benchmarks/guard_workloads.py`. These are not representative-workload false-denial rates or deployment latency estimates. Before presenting this as a broader empirical security paper, add an independently implemented stronger baseline, held-out attacks from an external reviewer, realistic benign workloads, a real authenticated tool-server integration, and restart/failure-injection tests around external effects. Report negative results. Those experiments are not prerequisites for an accurately scoped practitioner talk, but their absence limits the research claim.
