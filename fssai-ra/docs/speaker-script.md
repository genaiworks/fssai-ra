# Speaker script for the superseded 14-slide PowerPoint

> **Superseded. Do not rehearse from this.** The maintained deck is
> [`presentation/slides.html`](presentation/slides.html) with
> [its script](presentation/speaker-script.md). This script and the PowerPoint it
> matches predate the oversight ceiling, the second domain and the adversary
> corpus, and are kept only for provenance.

Working allocation: eight minutes. This script
matches `docs/trust-by-construction-final.pptx`; the browser deck has a different
sequence. Baseline results come from v1.0.0. Slide 11 presents a separately
identified current-source supplement. The deck notes contain source links.

## 1. Trust by Construction

20 seconds. A model may propose an action. It cannot create the authority to
execute it. Our contribution is a reference framework for expressing that rule,
testing when it fails, and teaching the institutional responsibilities around it.
The implementation is public and designed for others to extend.

## 2. A refused student asks three simple questions

35 seconds. Imagine a student receiving an adverse support decision. Who decided?
What did they see? How can I contest it? These questions give us requirements for
identity, evidence and a human route to correction. The example is synthetic.
An injected instruction and an ordinary model error can both cause harm. Testing
the authority boundary addresses only part of that problem.

## 3. Sovereignty as a capability set

30 seconds. We define sovereignty through powers an institution can actually
exercise: control of access, models, keys, policy, evidence and exit from a
dependency. Local hosting can contribute, but location alone does not settle
operator access or key custody. Contracts, governance and security controls
remain necessary. We do not claim that hardware makes a system inherently trusted.

## 4. Five domains

40 seconds. Import controls the inbound path. Transport supports ordered replay.
Versioned data preserves what the system used. Bounded assistance lets the model
prepare proposals. Accountable action places a separate executor before a state
change. These are responsibilities that can map to different technologies. The
model process must not hold the executor's write credential. A data diode constrains
one physical link when actually deployed and verified. It does not sanitize meaning
or close every other output channel.

## 5. The seven-field control contract

35 seconds. For each consequential capability, specify the asset, permitted
operation, enforcement point, accountable owner, failure test, evidence and
failure response. The contract connects policy to an observable result. Another
institution can change the domain and implementation while retaining the testable
obligations. The contribution is this integration, not a claim to have invented
least privilege, human approval or transaction processing.

## 6. Approval binds to one exact proposal

40 seconds. The officer approves the canonical proposal digest. The executor
checks the actual operation, target, evidence version, reviewed record version,
reviewer role, expiry and audience. An altered proposal needs a new approval.
The model's explanation supplies no authority. In the enhanced implementation,
the stored receipt also retains the proposal digest, so reusing a request ID
cannot substitute an unrelated earlier result.

## 7. The one-minute demonstration

50 seconds. Show the synthetic case and its valid approval. Change the target
after approval: the executor rejects the mismatch without changing the register.
Execute the original: one mutation and a receipt. Retry it: the same receipt.
Inspect the two evidence records. These are observed fixture behaviors. They do
not prove that a live model followed a malicious prompt, which needs a separate
model experiment. Use a captured run if the live demo fails.

## 8. Containment beside utility

35 seconds. The fixed v1.0.0 baseline contains 30 of 30 declared adversarial
scenarios and completes six of six benign tasks. It reports eight control
ablations, 240 bounded configurations and 187 collected tests at release.
Say the denominators. A system that refuses everything is not useful. Test
counts describe the artifact; they are not a scientific quality score.

## 9. Controlled comparison

35 seconds. The three arms use seven synthetic attacks. The unguarded arm contains
none, the prompt-and-allowlist arm contains two, and the complete architecture
contains seven. The comparison isolates architectural controls under fixed inputs.
It does not estimate field attack rates or compare commercial model quality.
Useful task completion is reported alongside the containment result.

## 10. Tests that expose defects

30 seconds. A useful assurance process must be capable of rejecting its own
implementation. Earlier checks exposed shallow tests and an adapter credential
problem. The current review also found the replay-identity weakness and a database
lock-release issue. We corrected them and kept regression tests. Remaining
qualification gaps are documented, including PostgreSQL concurrency.

## 11. Independent processes and crash recovery

45 seconds. This is supplemental evidence beyond v1.0.0. Eight independently
connected processes retry one approved request: one mutation, one receipt and
seven replay responses. A second race uses competing approvals for the same
record version: one succeeds and seven receive conflicts. Four process exits
around commit recover the expected state. Before commit, nothing is durable;
after commit, the complete record survives and retry returns it. These are local
SQLite observations. Power loss and distributed failures remain untested.

## 12. Replaceable implementation components

30 seconds. Python and FastAPI expose the workflow. Redis, Kafka, PySpark and
Iceberg serve different storage and processing roles. The smaller fixture profile
lets people learn without operating that entire stack. A replacement adapter
must pass its own conformance and failure tests. Passing SQLite tests does not
qualify PostgreSQL, a distributed deployment, or a physical diode.

## 13. Both halves of the conference theme

30 seconds. For AI for Learning, the framework supports governed educational
workflows. For Learning for AI, staff and students can inspect permissions,
remove a control, observe a failure and test recovery. Institutions can share
tests without sharing learner records. Educational benefit, reviewer workload,
accessibility and costs still require domain-specific studies.

## 14. Closing

25 seconds. For your next AI pilot, ask for the prohibited action, its failure
test, the evidence retained, and the person responsible for restoring service.
The public repository gives you a base to reproduce and extend. We welcome
independent reproduction and domain profiles. The framework can make an action
attributable. It cannot by itself make the underlying policy fair.
