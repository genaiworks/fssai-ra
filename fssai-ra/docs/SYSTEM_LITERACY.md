# From model literacy to system literacy

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Policy leader → [`PROCUREMENT.md`](PROCUREMENT.md) · educator → [`LAB.md`](LAB.md) · engineer → [`PLATFORM.md`](PLATFORM.md)

Knowing what a model can generate is not enough to govern what an agent can do.
**System literacy** is the ability to trace a consequential action across data,
delegation, verification, escalation, and accountability — and to test where
authority is granted, checked, exercised, recorded, and recovered.

This is a teaching framework and an assessment design built on the executable
reference architecture. It does **not** claim measured learning gains; no learner
study has yet been conducted.

## The five literacies

| Literacy | Learner can answer | Repository exercise | Inspectable artifact |
|---|---|---|---|
| **1 · Data** | Where did this evidence come from, what crossed the boundary, and which version was used? | Reject an invalid import; replay an event; inspect a snapshot | quarantine reason, event identifier, lineage record, snapshot manifest |
| **2 · Delegation** | Which power was delegated to the agent, which was withheld, and who holds the real write credential? | Propose an allowed action and an unauthorised one; trace both to the enforcement point | capability grant, control contract, proposal digest, denial code |
| **3 · Verification** | What was checked independently of the model, and what does that check not prove? | Run bounded verification, conformance, ablation, and the decision-packet forgery lab | invariant result, conformance check, ablation result, packet verdict |
| **4 · Escalation** | When must automation stop, who takes over, and can that person genuinely review the load? | Compute an oversight ceiling; exceed it; observe deferral to the manual path | capacity declaration, headroom, escalation, recovery owner |
| **5 · Accountability** | Who authorised the exact action, what did they see, what happened, and how can an affected person seek correction? | Inspect proposal → approval → receipt; attempt replay; contribute a failure case | evidence chain, decision packet, replay receipt, correction or appeal route |

These literacies are deliberately about systems rather than brands. FastAPI,
Redis, Kafka, PySpark, Iceberg, a local model, and a data diode are examples of
components that can discharge specific duties. Naming the technology is not the
learning outcome; explaining its duty, limit, failure test, and replacement seam
is.

## Learning sequence

### 1. Data literacy: provenance before prompting

Learners follow one synthetic record through validation, quarantine, transport,
transformation, and snapshotting. They distinguish:

- provenance from truth;
- a source signature from benign content;
- replayability from exactly-once effects;
- version history from fairness.

The one-way interface in the teaching profile has no read-back method. That is a
software-enforced seam, not a physical non-interference proof. A certified
hardware diode can strengthen that one link, but it does not govern other
network, administrative, removable-media, or side-channel paths.

### 2. Delegation literacy: authority before autonomy

Learners convert one institutional capability into a seven-field control
contract. They identify what the model may read, propose, and never execute.
Then they locate the separate policy and execution components that own the
decisive checks and credentials.

The assessment is behavioural: an unauthorised proposal must be possible to
express and impossible to turn into a mutation. A model that is merely prompted
not to act has not passed.

### 3. Verification literacy: evidence before assurance language

Learners run four different checks because each answers a different question:

1. scenario evaluation — did sampled hostile and benign workflows behave as
   declared?
2. bounded verification — do invariants hold throughout the declared finite
   authority space?
3. ablation — does removing a named control restore the harm?
4. conformance — do the same properties survive a backend substitution?

The decision-packet lab adds an epistemic limit: internally consistent records
can still describe a false history. A separately retained fingerprint detects a
coherent rewrite; it still does not establish that the underlying evidence was
true or the decision just.

### 4. Escalation literacy: human review as capacity

Learners stop treating “human in the loop” as a binary feature. They declare a
roster, quota, review window, and deliberation floor, compute the sustainable
ceiling, and decide what the manual fallback will do when demand exceeds it.

They must defend the assumptions rather than optimise the number. Lowering the
declared reading time to manufacture capacity is not an improvement. Real
reviewer accuracy, fatigue, accessibility, and queue effects require empirical
study and remain open work.

### 5. Accountability literacy: contestability as an institutional process

Learners reconstruct a decision from the proposal, exact approval, execution
receipt, and selected evidence records. They identify the named role responsible
for correction or appeal and the route by which an affected person can reach
that role.

The implementation demonstrates evidence production, replay control, and
reconciliation. It does not implement or validate the quality, timeliness,
accessibility, or fairness of a real appeal process. Those are institutional
obligations that the architecture can support but cannot satisfy by itself.

## A 90-minute teach-and-test format

| Time | Activity | Observable learner output |
|---|---|---|
| 0–10 | Complete one authority-boundary worksheet | one seven-field control contract |
| 10–25 | Force an independent refusal | denial code and identified enforcement point |
| 25–40 | Remove the control | reproduced harm and revised claim |
| 40–60 | Calculate the oversight ceiling | assumptions, capacity, headroom, fallback decision |
| 60–75 | Forge and verify a decision packet | explanation of inconsistent vs unanchored vs anchored |
| 75–85 | Add one domain attack | non-executable YAML challenge with expected harm |
| 85–90 | Publish the boundary | authorisation boundary, failure test, recovery owner |

The facilitator script and commands are in [`LAB.md`](LAB.md). A self-directed
code-reading version is in [`START_HERE.md`](START_HERE.md).

## Assessment rubric

Score each dimension `0` (asserted), `1` (identified), or `2` (demonstrated).

| Dimension | 0 · asserted | 1 · identified | 2 · demonstrated |
|---|---|---|---|
| Boundary | says “secure” | names a boundary | produces an action the boundary refuses |
| Delegation | says “human controlled” | names roles | shows the model lacks the execution credential |
| Verification | cites a test count | names test types | reproduces a result and its limit |
| Escalation | says “human in loop” | names a fallback | computes capacity and triggers deferral |
| Accountability | says “auditable” | names records | reconstructs one decision and identifies correction route |
| Transfer | repeats the example | drafts a new profile | runs the same suite without changing library code |

A learner has reached the baseline when every row scores at least `1` and at
least four rows score `2`. This threshold is a proposed assessment rule, not a
validated psychometric instrument.

## Research agenda

The reference implementation makes future educational research reproducible.
Useful next studies include:

- pre/post comparison of system-literacy rubric scores;
- transfer to health, benefits, justice, or licensing cases;
- reviewer accuracy and fatigue under observed, consented workloads;
- accessibility and comprehension of decision packets for affected people;
- appeal timeliness and correction quality;
- cost and energy comparison across deployment profiles;
- independent red-team contributions to the adversary corpus.

The repository supplies instruments and testable hypotheses. It does not treat
those future measurements as present results.
