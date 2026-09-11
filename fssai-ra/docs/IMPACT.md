# Who benefits, how, and how we would know

A humanitarian claim that cannot name a beneficiary is a slogan. This document
names them, says what each gets, and — where nothing has been measured — says
that instead of estimating.

Nothing here is a deployment claim. There is no institutional deployment, no
pilot, and no field data. What follows is a reasoned case with its evidence
status marked on every line, using four labels:

- **Demonstrated** — an artifact in this repository does it, with a test.
- **Reasoned** — follows from what is demonstrated, but not itself measured.
- **Hypothesis** — plausible, untested, and stated as a research question.
- **Out of scope** — the architecture does not address it, and pretending
  otherwise would be the harm.

---

## The primary beneficiary is the person the decision is about

Not the institution, and not the operator. When an agent participates in a
decision about a student's support, a patient's referral, or a household's
benefit, the person affected carries the consequence of it being wrong — and has
the least ability to find out that it was.

| What they get | Evidence status |
|---|---|
| A consequential decision cannot be made without a named person authorizing that exact change | **Demonstrated** — 0 unauthorized mutations across 30 scenarios and 240 checked configurations |
| A record of who authorized it, against which evidence version, that the system's operator cannot silently edit | **Demonstrated** — hash-chained ledger with a separate write credential; alteration and truncation both detectable |
| A decision refused by automation still reaches a person, on a stated timescale | **Reasoned** — the manual fallback is a required, named field in every profile (`XC-4`), and profiles without one fail validation. Whether institutions honour it is untested |
| An explanation they can actually use to appeal | **Hypothesis** — the evidence artifact is specified per requirement, but whether a real applicant can use it is a human-factors question nobody here has studied |
| Fair treatment | **Out of scope.** The architecture governs *who may act on what evidence*. It cannot make an inequitable eligibility rule equitable |

The honest summary: this makes a decision **challengeable**. It does not make it
correct, and it does not make it fair.

## The caseworker, officer, or clinician

| What they get | Evidence status |
|---|---|
| Assistance that drafts and assembles, without the ability to decide | **Demonstrated** — the model proposes; the enforcement point disposes; verified against a deliberately compromised backend |
| Confidence that what they approve is what happens | **Demonstrated** — approval binds to the canonical proposal digest; any change requires renewed review |
| No silent double-execution when the network fails | **Demonstrated** — idempotent retry returns the stored receipt; single-transaction durability where register and ledger share a database |
| Less time on assembly, more on judgement | **Hypothesis** — time saved is not measured. This is the most commonly claimed benefit in this space and the one we have the least right to assert |
| Protection from being blamed for a machine's error | **Reasoned** — the record distinguishes what the agent proposed from what a person authorized, which is the prerequisite for that protection, not the protection itself |

## The institution

| What they get | Evidence status |
|---|---|
| A capability-by-capability basis for deciding what to automate | **Demonstrated** — the seven-field contract, with validation that fails on an empty or unactionable field |
| The ability to replace a vendor component without losing the assurance argument | **Demonstrated** — 25-check conformance suite passing on 2 independent backend profiles |
| A supplier conversation grounded in enforcement rather than assurance language | **Demonstrated** as an artifact ([`PROCUREMENT.md`](PROCUREMENT.md)); its effect on procurement outcomes is untested |
| Evidence that survives staff turnover and vendor change | **Reasoned** — the record is append-only and the contract is enforced configuration rather than a wiki page |
| Reduced cost | **Hypothesis.** Not measured. Hardware, utilisation, maintenance, and staff time all cut against it |

## Institutions with little money and no cloud budget

This is where the design choices matter most, and where they were made
deliberately.

| What they get | Evidence status |
|---|---|
| Every claim in this repository verifiable offline, on a laptop, in under two seconds | **Demonstrated** — 160 tests, a 240-state model check, and the full evaluation, with no network, no GPU, and no model weights |
| A durable single-institution deployment without a cluster | **Demonstrated** — SQLite is a first-class transactional profile, not a toy; it is what CI uses to prove the atomicity property |
| Independence from any commercial model | **Demonstrated** — the default is local; the deterministic backend needs no weights; every control is measured with the model assumed hostile |
| The ability to audit us rather than trust us | **Demonstrated** — this is the whole point of reproducing offline. An institution that cannot afford to run a model can still check every number here |
| Capacity built by exchanging tests and failure cases, not data | **Reasoned** — the conformance suite and contract are designed to be shared; no student record ever needs to move |

## Beyond education

The architecture is domain-neutral; the reference profile is not. `fssaira init`
scaffolds a new domain, and the worksheet walks a capability through the seven
fields. Three adjacent domains carry the same shape — a consequential state
transition on a record about a person, with a professional accountable for it:

- **Clinic referral triage** — a priority band changed on a waiting list.
- **Benefits eligibility** — a claim advanced to caseworker decision, with a
  statutory clock attached.
- **Licensing and permits** — an application moved toward a decision that
  carries a legal effect.

All three appear as worked examples in the worksheet. **Evidence status:
reasoned.** The structure transfers; none of these has been piloted, and each
would need its own contract, its own failure tests, and its own assurance file
written from its own results.

## How we would know it worked

An impact claim needs a measurement plan, not an estimate. Ordered by what a
first pilot could realistically produce:

| Measure | Method | Why it is not here yet |
|---|---|---|
| Unauthorized actions completed per attempt | Already instrumented; runs on synthetic fixtures | Needs a real workflow to be meaningful |
| False-denial rate on real cases | Already instrumented; currently 0.0 on 6 synthetic tasks | A synthetic suite bounds over-restriction; it does not predict field rates |
| Time from denial to a served applicant | Time the manual fallback with a real person | Requires a pilot and a consenting service |
| Reviewer accuracy on misleading recommendations | A review exercise with a control condition | Requires human subjects and ethical approval |
| Appeal success rate where evidence was produced | Compare against the pre-existing baseline | Requires a year of operation |
| Whether the evidence is usable by the affected person | Accessibility and comprehension testing in local languages | Not started |

The first two are running today. The rest are the work, and none should be
claimed before it is done.

## The limit worth restating

Containing an agent's authority is necessary and nowhere near sufficient for
benefit. A perfectly governed agent enforcing an unjust policy produces
well-documented injustice, faster. This architecture's contribution is that the
injustice would be **attributable** — a named person authorized it, against a
recorded evidence version, and the record cannot be quietly edited.

That is a real contribution and a modest one. It should not be described as
anything more.
