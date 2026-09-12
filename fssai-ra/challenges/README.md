# The open adversary corpus

Every attack this architecture is measured against was written by the people who
built it. That is the standing weakness of the evidence, and internal rigour does
not repair it: a suite written by the author of a defence samples the author's
imagination, and the interesting failure is always the one nobody on the team was
equipped to imagine.

This directory is the mechanism for fixing that, and it is open now rather than
after the corpus is respectable.

```bash
fssaira challenge --dir challenges
```

Each contributed attack runs against three architectures — an unguarded agent, a
prompt-guarded agent, and this one — and the report names who contributed it.

## Contribute one

Copy [`TEMPLATE.yaml`](TEMPLATE.yaml), fill in seven fields, open a pull request.

You do **not** need to share a student record, a deployment detail, a vendor
name, or anything your institution would have to clear. An attack here is data:
the grant an agent legitimately holds, and what a compromised model then
proposes. Nothing you write is executed as contributor code, so an institution
can adopt the corpus without auditing it.

| Field | What it is |
|---|---|
| `challenge_id` | unique; a short slug is fine |
| `title` | one line naming what the adversary is trying to achieve |
| `submitted_by` | you or your institution — this is the attribution |
| `description` | the sentence you would use to explain the risk to a colleague who does not work in security |
| `grant` | the tools the agent legitimately holds |
| `proposals` | what the compromised model proposes, including the action class it *claims* |
| `expected_harms` | which harms land if nothing stops it |

The runner checks your `expected_harms` against what the unguarded arm actually
did and tells you when the two disagree, so a mistaken expectation is caught on
your machine rather than in review.

## What the corpus does and does not establish

An attack contained by Arm C is evidence about *that attack*, against *these
fixtures*. A hundred contributed attacks, all contained, would still not be a
security certification.

What they would be is a claim with a denominator somebody else controls. That is
strictly more than any suite written entirely in-house can offer, and it is the
reason to build the mechanism before the corpus is large rather than after.

The report prints `externally_contributed` for exactly this reason. At the time
of writing it is **0**: every challenge here is maintainer-authored, and the
corpus therefore still samples the maintainers' imagination. That number is the
one to watch, and it is printed in the tool rather than buried in a limitations
paragraph.

## What is in here now

Ten entries, and they are not all attacks — a corpus of attacks alone measures
only how much a system refuses, and a system that refuses everything scores
perfectly.

| | |
|---|---|
| Live attacks, contained by this architecture | 7 of 7 |
| Contained by an unguarded agent | 0 |
| Attacks stopped before any harm could land | 2 |
| Negative controls — legitimate work that must succeed | 1 |
| Contributed from outside this project | **0** |

`fssaira challenge` also reports which harms the corpus actually exercises and
which denial controls it reaches, derived from the run rather than from a
taxonomy asserted here. Referencing a published risk class records intent; it is
not evidence of covering that class, and the report says so.

## What contributing has already been worth

The first challenge run through this mechanism found a defect — in the
measurement, not the architecture. `maintainers-2026-002` carries records out in
the arguments of a tool that is *not* classified as egress. The enforcement point
refused it correctly (`EGRESS_IN_ARGUMENTS`). But the harm counter was keyed on
tool names, so it recorded no harm at all, scored the attack "inert", and would
have reported that the unguarded arm contained it.

A measurement blind to a class of harm under-reports the gap between the
architectures it compares, and it errs in the direction that flatters the system
under test. The counter now detects harm by effect. The published comparison
figures were unchanged — that attack set never reaches the blind spot — and
`tests/test_challenge.py` pins them so a future correction cannot quietly move
them.

That is one defect from a handful of attacks written by the same team that wrote
the defence. Writing the corpus also caught a second, smaller thing: an attack
built to test the per-agent call budget sent exactly the budgeted number of calls
and saw nothing refused. A contributor would have concluded no budget existed.
The entry now sends more than the budget and says why in its description.

Both are reasonable advertisements for what a corpus written by other people
would find.

## A note on scope

This corpus tests the **authority boundary**: whether a proposal can become an
institutional action without the authority to do so. It does not test model
quality, retrieval accuracy, or whether a decision was fair or kind. A
well-contained architecture enforcing an unjust policy produces well-documented
injustice. Attacks on *that* problem are welcome in the issue tracker; they are
not what this runner scores.
