# The Mediation Thesis

> **Canonical framework:** [Trust by Construction](FRAMEWORK.md) · [P1–P34 catalogue](framework/PATTERNS.md) · [Operational controls](framework/CONTROLS.md). This guide is a supporting view of that single framework.

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Run `fssaira thesis` to try to refute it, then read the obligations in [`SPECIFICATION.md`](SPECIFICATION.md).

## The thesis

> **Intelligence is untrusted. Power and data are mediated. Trust requires independently checked evidence and bounded visibility.**

Every AI system that can affect people, records, resources, or confidential
information should be built on one foundation. The model reasons. It never holds
the power to act or the right to see. Both belong to mediators that the model
cannot bypass, influence, or impersonate. Those mediators decide from
institutional state, and every decision they make is contracted, tested, and
evidenced in the deployment that relies on it.

This page states the thesis precisely, derives the rest of the framework from it,
says what would refute it, and says what an institution does next.

## Three commitments

**1. Untrusted intelligence.** Treat every model as capable, persuasive, and
possibly mistaken, manipulated, or misaligned. Treat its output as a proposal or a
request, never as a decision. Treat its account of itself, including how risky an
action is or how sensitive a summary is, as untrusted input.

**2. Mediated power.** Every effect on the world and every flow of protected
information passes through a mediator outside the model. The mediator alone holds
the credential. It checks purpose, authority, consent, version, and location at the
moment of use, and it fails closed to a named human route.

**3. Evidenced trust.** Trust is claimed, never assumed. Each mediation has a
contract with an owner, a failure test that runs, and evidence that reconstructs
intent and outcome. A deployment claims conformance by class and regenerates its
evidence. It does not inherit anyone else's.

## Two rules that follow

> **R1.** A model may propose an action. It cannot manufacture the authority to
> execute it.
>
> **R2.** A model may request information. It cannot manufacture the entitlement to
> see it, and it cannot launder what it saw.

R1 is commitment 2 applied to effects. R2 is commitment 2 applied to information.
Commitment 1 is why neither rule may depend on the model's behaviour. Commitment 3
is why each rule is a set of tests rather than a policy sentence.

## The invariants, stated precisely

Write *E* for any governed effect, *D* for any disclosure of protected data to a
context or recipient, and *t* for the moment it happens.

- **Effect.** *E* occurs at *t* only if an approval bound to the exact proposal
  digest of *E* exists, was issued by an authority other than the proposer, is
  unexpired and unused at *t*, and the resource version at *t* equals the reviewed
  version.
- **Disclosure.** *D* of data with label *L* to destination *x* occurs at *t* only if
  a grant held by the requester covers the purpose, subjects, fields, and classes of
  *L* at *t*, consent permits the purpose at *t*, and *x* dominates *L*. Otherwise
  an independent declared role lowered *L* for that exact output.
- **Composition.** Authority conferred by a delegation chain is the intersection of
  the grants along it. The label of derived data is the join of everything it was
  derived from. Authority only narrows. Restriction only accumulates.
- **Evidence.** Neither *E* nor *D* occurs unless its intent was recorded first, by
  a writer the model cannot impersonate, without copying protected values.

## What would refute it

The thesis is falsifiable. It is refuted, for a declared scope, by any one of these.

| Falsifier | Refuting observation |
|---|---|
| **F1 Unmediated effect** | a model output alone causes a governed state change |
| **F2 Unentitled read** | protected data reaches a model context without a current, holder-bound, purpose-bound grant and consent |
| **F3 Laundered release** | an output reaches a recipient that does not dominate its label, or is released after consent, revocation, or expiry should have stopped it |
| **F4 Amplified delegation** | a delegation chain confers more authority than its root |
| **F5 Decorative control** | removing a control lets no harm through, so the control was not doing the work claimed |
| **F6 Phantom evidence** | a contract requirement, threat claim, or specification requirement cites evidence that does not exist or runs nothing |

`fssaira thesis` runs every falsifier against every declared domain pack and
prints the bounded attempts, the counterexamples, and the scope. A run with zero
counterexamples means *not refuted within the stated bounds*. It never means
proven.

The suite is itself tested for the ability to fail. Removing a single mediator
check makes the falsifiers find counterexamples, which is how a reader knows the
zero is not produced by a test that cannot see.

## What it predicts

A thesis worth building on should say something that could turn out wrong.

1. **Model capability and system safety decouple.** Replacing a weak model with a
   strong or adversarial one changes utility, not the mediated invariants. If more
   capable models break the invariants, the mediation is incomplete.
2. **Harm migrates to the trusted base and to granted authority.** Once mediation
   holds, remaining incidents concentrate in compromised administrators and keys,
   undeclared interfaces, wrong decisions inside legitimate authority, and unjust
   rules. Those are exactly the residuals the threat catalogue names.
3. **Conventional access control leaks on purpose, consent, and derived data.**
   Designs that check roles and classes but not purpose, live consent, and output
   labels will fail the same flows here, whatever their vendor.
4. **Single-step testing misses sequence defects.** Enumeration of one decision at a
   time will pass designs that stateful testing refutes. This happened in this
   repository.

## What an institution does next

The foundation is only useful if it changes what a team does on Monday.

| Horizon | Action | Output you can show |
|---|---|---|
| **This week** | Pick one consequential capability and one sensitive read. Name the mediator and the credential only it holds. | a filled [worksheet](worksheet/) and a trusted-base list |
| **This month** | Write the seven-field contract and a domain pack with purposes, classes, zones, recipients, and fallback. Run `fssaira thesis` on it. | falsifier results with denominators, residuals stated |
| **This quarter** | Place the mediators in front of a synthetic copy of the real system. Claim conformance by class. | a conformance claim against [`SPECIFICATION.md`](SPECIFICATION.md) with local evidence |
| **Before production** | Configure durable state, institutional grants, live consent, and real record sources; run the pilot protocol; independent assessment and drills. | `fssaira pilot-report` indicators, the outcomes in [`PILOT_PROTOCOL.md`](PILOT_PROTOCOL.md), and a go or no-go decision |

## What the field should build next

A foundation invites shared infrastructure. These are the pieces no single
institution should build alone.

- **Interoperable grant and label formats** so mediators from different vendors can
  exchange purpose-bound entitlements and data labels.
- **Certified mediators** whose small trusted code is independently verified, the
  way cryptographic modules are today.
- **Conformance registries** where deployments publish their claims, evidence
  kinds, and residuals.
- **Shared adversary corpora** of failure cases that travel without records.
- **Field measurements** of reviewer accuracy, re-identification, and harm inside
  granted authority, which no software test can supply.

## What the thesis does not claim

It does not claim alignment, fairness, legal compliance, or security against a
compromised trusted base. A mediated system can faithfully enforce an unjust rule,
and a model can still do harm inside the authority it was legitimately granted. The
thesis moves those problems into the open, where governance, oversight, and
contestability can reach them. It does not make them disappear.

## Where the rest of the framework comes from

| Framework element | Derived from |
|---|---|
| Seven planes in [`REFERENCE_ARCHITECTURE.md`](REFERENCE_ARCHITECTURE.md) | where mediators sit and what they must hold |
| Seven laws and patterns in [`PATTERNS.md`](PATTERNS.md) | how to build mediators that satisfy the invariants |
| Governed disclosure in [`GOVERNED_DISCLOSURE.md`](GOVERNED_DISCLOSURE.md) | R2 made executable |
| Normative requirements in [`SPECIFICATION.md`](SPECIFICATION.md) | the commitments as MUST and SHOULD |
| Threat catalogue and residuals in [`ASSURANCE.md`](ASSURANCE.md) | commitment 1 tested against real failure classes |
| Positioning in [`RELATED_WORK.md`](RELATED_WORK.md) | the reference monitor and information-flow traditions this extends |
