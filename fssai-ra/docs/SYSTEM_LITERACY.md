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
| **2 · Delegation** | Which power was delegated to the agent, which was withheld, who holds the real write credential — and what happens when the agent delegates onward? | Propose an allowed action and an unauthorised one; trace both to the enforcement point. Then build a two-hop chain, widen it, and watch the chain verifier refuse | capability grant, control contract, proposal digest, denial code, delegation chain verdict |
| **3 · Verification** | What was checked independently of the model, and what does that check not prove? | Run bounded verification, conformance, ablation, and the decision-packet forgery lab | invariant result, conformance check, ablation result, packet verdict |
| **4 · Escalation** | When must automation stop, who takes over, can that person genuinely review the load — and is their AI assistant a second opinion or the same one twice? | Compute an oversight ceiling; exceed it; observe deferral to the manual path. Then enable review assistance and compare a dependent assistant with an independent one | capacity declaration, headroom, escalation, recovery owner, assistance declaration |
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

Then the second half, which is where most real systems now live. Learners build a
chain — an orchestrator delegating to a sub-agent, which delegates again — and
try four things in turn: hand onward more authority than they hold; present a
sibling's chain as their own; let a delegation outlive the grant it descends
from; and do a narrow agent's work under a broad agent's grant. Each is refused
with a named code, and `fssaira delegation` shows the same chains against an
unguarded architecture and against one that checks each hop against its
immediate delegator only.

That middle column is the lesson. Per-hop validation is a real control and it is
what most learners will build if asked; it contains two of ten risk classes
because it cannot see the root. **Every hop locally correct, the composition
wrong** is the sentence to leave with, and it transfers well beyond agents.

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

Then the exercise most learners will actually face in post. Give the reviewer a
model assistant and the numbers improve immediately: five times the completed
work, no deferrals. Ask learners to lower the deliberation floor accordingly —
which is correct, because an assisted reviewer genuinely decides faster — and
then run the same queue with an assistant that shares the proposing model and
its evidence packet.

The merit failures come back, and nothing anywhere says so: the chain is intact,
the reviewer is inside quota, every approval clears the floor, no refusal fires.
Learners should sit with that for a moment before being shown the control, which
binds at *configuration* time for the reason they will have just discovered —
at runtime the two deployments are identical.

The transferable judgement is not about models. It is that **a check which
shares its subject's reasoning is not a check**, and that the property doing the
work — independence — has to be declared before it can be required. The three
declarations (a different model, a different evidence path, an adversarial
posture) are the assessable artifact; the correlation between them is a declared
parameter here and measuring it on real systems is open work.

### 5. Accountability literacy: contestability as an institutional process

Learners reconstruct a decision from the proposal, exact approval, execution
receipt, and selected evidence records. They identify the named role responsible
for correction or appeal and the route by which an affected person can reach
that role.

The implementation demonstrates evidence production, replay control, and
reconciliation. It does not implement or validate the quality, timeliness,
accessibility, or fairness of a real appeal process. Those are institutional
obligations that the architecture can support but cannot satisfy by itself.

## A two-hour teach-and-test format

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
