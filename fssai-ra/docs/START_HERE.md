# Understand this repository, step by step

This is the shortest route from “I cloned it” to “I can explain, test, and
extend it.” It takes about 75 minutes and stays offline after installation.

The one idea to keep in your head is:

> **A model may propose an action. It cannot manufacture the authority to
> execute it.**

Do not begin with Kafka, Spark, or the data diode. Those are replaceable
implementations. Begin with the authority boundary; then see how each technology
serves it.

## Step 0 · Draw the system in one line (2 minutes)

```text
untrusted record → controlled import → durable event → reproducible evidence
                 → model proposal → policy + human approval → separate executor
                 → receipt + independently checkable decision packet
```

The model is intentionally in the middle, not at the end. It can interpret and
propose. A different component owns the credential that changes institutional
state.

## Step 1 · Install the teaching profile (5 minutes)

From the outer repository directory:

```bash
cd fssai-ra
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
```

The suite should pass without Docker, a network connection, model weights, or a
GPU. The in-memory and SQLite components are executable teaching substitutes;
they are not evidence that the distributed deployment is production-ready.

## Step 2 · Watch one safe and one unsafe action (5 minutes)

```bash
python scripts/demo.py --fast
```

While it runs, ask two questions:

1. What may the model propose?
2. Which component has the credential that can actually change the case?

The answer to the second question should never be “the model process.” Read
[`docs/DEMO.md`](DEMO.md) if any act in the demonstration is unclear.

## Step 3 · Read the policy before the Python (8 minutes)

Open [`profiles/student_support.yaml`](../profiles/student_support.yaml). Find:

- the actors and capabilities;
- the allowed state transitions;
- which transitions are consequential;
- the required reviewer role;
- the manual fallback;
- reviewer capacity and deliberation assumptions.

Then open [`src/fssaira/contract.py`](../src/fssaira/contract.py). The seven-field
control contract links a governance claim to a protected asset, operation,
enforcement point, owner, failure test, evidence artifact, and recovery response.
If one field cannot be named, the capability is not ready to automate.

## Step 4 · Trace one request through the code (12 minutes)

Read these files in this order:

1. [`src/fssaira/control_plane.py`](../src/fssaira/control_plane.py) — the
   propose → approve → execute orchestration.
2. [`src/fssaira/exact_action.py`](../src/fssaira/exact_action.py) — proposal
   digests, approval binding, expiry, role and audience checks.
3. [`src/fssaira/accountable_action.py`](../src/fssaira/accountable_action.py) —
   policy decisions for consequential actions.
4. [`src/fssaira/atomic_execution.py`](../src/fssaira/atomic_execution.py) — one
   mutation, replay receipts, and uncertain-outcome handling.
5. [`src/fssaira/evidence.py`](../src/fssaira/evidence.py) — the hash-chained
   evidence record.
6. [`src/fssaira/decision_packet.py`](../src/fssaira/decision_packet.py) and
   [`src/fssaira/packet_verifier.py`](../src/fssaira/packet_verifier.py) — export
   and offline inspection of the proposal, approval, receipt, and selected
   evidence records.

At every file, identify the **grant**, **check**, **state change**, **record**, and
**recovery path**. That five-word trace is more useful than memorising classes.

## Step 5 · Attack the boundary, then remove it (8 minutes)

```bash
fssaira evaluate profiles/student_support.yaml
```

Read [`src/fssaira/evaluation.py`](../src/fssaira/evaluation.py) beside the output.
The evaluation reports hostile containment and benign completion together. Then
it removes one control at a time. If removing a claimed control does not restore
the harm, that control was not carrying the claim.

This is the first important distinction:

- a policy says what should happen;
- an enforcement point prevents what must not happen;
- an ablation shows whether that enforcement point mattered in the fixture.

## Step 6 · Ask questions ordinary tests miss (8 minutes)

```bash
fssaira verify profiles/student_support.yaml
fssaira conformance --backend memory --profile profiles/student_support.yaml
fssaira conformance --backend sql --profile profiles/student_support.yaml
```

Read [`src/fssaira/verification.py`](../src/fssaira/verification.py) and
[`src/fssaira/conformance.py`](../src/fssaira/conformance.py).

- **Bounded verification** enumerates the declared authority space and checks
  invariants. It is not proof outside that bounded space.
- **Conformance** asks whether the same control properties survive when an
  institution replaces a backend.

## Step 7 · Discover why “human in the loop” is incomplete (7 minutes)

```bash
fssaira oversight profiles/student_support.yaml --sweep
```

Open the offline [oversight calculator](oversight/) and then read
[`src/fssaira/oversight.py`](../src/fssaira/oversight.py). The system treats
review attention as a finite, declared resource. Above the ceiling it defers to
the manual path instead of quietly turning approval into a signature service.
The degradation curve is a declared parameter, not measured human behaviour.

## Step 8 · Learn what a verified hash does not prove (7 minutes)

Use a fresh output name each time:

```bash
python scripts/decision_packet_lab.py --output /tmp/fssaira-packet-lab.json
```

The lab shows three different verdicts: inconsistent, internally consistent but
unanchored, and consistent against a separately retained fingerprint. A hash can
show that records agree. It cannot show that an event happened, an input was
true, or a decision was fair.

## Step 9 · Test whether the method travels (5 minutes)

```bash
make second-domain
```

Compare [`profiles/academic_record_correction.yaml`](../profiles/academic_record_correction.yaml)
with the first profile. The library should not change when the domain changes.
The new profile inherits the structure, not the first profile’s evidence.

## Step 10 · Contribute an attack, not a testimonial (5 minutes)

```bash
fssaira challenge --dir challenges
```

Copy [`challenges/TEMPLATE.yaml`](../challenges/TEMPLATE.yaml), describe a failure
from your domain, and score it. Entries are data, not executable contributor
code. A failure the architecture does not contain is a useful result.

## Step 11 · Map the teaching seams to the distributed stack (5 minutes)

Only now read [`docs/PLATFORM.md`](PLATFORM.md) and
[`deploy/compose.yaml`](../deploy/compose.yaml).

| Conceptual duty | Teaching implementation | Distributed reference component |
|---|---|---|
| HTTP control plane | direct Python calls | FastAPI in `src/fssaira/api.py` |
| durable state and replay guards | memory / SQLite | PostgreSQL and Redis adapters |
| ordered, replayable events | in-process event log | Apache Kafka |
| lineage transform | `Transformer` | PySpark job |
| versioned evidence snapshots | `SnapshotStore` | Apache Iceberg + object storage |
| bounded proposal engine | deterministic/adversarial fixture | local model adapter, e.g. Ollama |
| one-way release seam | software no-read-back interface | deployable hardware data diode |

The table is a mapping, not an equivalence claim. A Python interface cannot
prove physical directionality; a single Docker host cannot provide independent
administrative trust.

## Step 12 · Extend it safely (8 minutes)

```bash
fssaira init my_domain --output /tmp/fssaira-my-domain
```

Follow [`docs/EXTENDING.md`](EXTENDING.md). Replace the generated example with
one real consequential capability and write the failure test before adding real
records, credentials, or a model. The scaffold’s assurance file starts empty on
purpose.

## You understand the repository when you can teach back this checklist

- I can name the protected asset and exact consequential operation.
- I can show that the model lacks the mutation credential.
- I can point to the policy-independent enforcement point.
- I can explain what the approval digest binds and why stale approval fails.
- I can identify the manual fallback and its accountable owner.
- I can reproduce a denial, remove its control, and make the harm return.
- I can explain the oversight ceiling using my institution’s own assumptions.
- I can distinguish tamper-evidence from truth, fairness, and non-repudiation.
- I can state which claims are fixture observations and which remain unevidenced.
- I can add a domain without copying another domain’s assurance claims.

For a facilitated version of this path, continue with
[`docs/LAB.md`](LAB.md). For a claim-by-claim audit, use
[`docs/REVIEWERS.md`](REVIEWERS.md) and run `make reviewer`.
