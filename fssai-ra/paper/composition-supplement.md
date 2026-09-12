# Composition supplement: delegated authority and assisted review

This supplement records the two contributions the extended abstract states in
compressed form: what happens to authority when an agent passes it to another
agent, and what happens to human oversight when the reviewer also has a model.
It supports discussion and a future full paper. It is not an additional field to
paste into the conference form, and it changes no denominator of the earlier
containment experiment.

Both contributions share a shape worth naming up front. Neither is a *model*
failure. In both, every component behaves exactly as specified, every mechanism
passes its tests, and the harm arrives anyway — because the defect is in a
composition no single component can see. That is precisely the class of problem
an architecture is for, and precisely the class a better model does not fix.

---

## Part I — Delegated authority

### Research question

When an agent's authority is passed to another agent, and from there to a third,
does the institution retain a bounded, attributable answer to *who was allowed to
do this* — and does any hop acquire authority its grantor did not hold?

### Why the single-agent model is no longer sufficient

Every other control in this architecture answers one question about one
`agent_id`. That was the right model for the agent of 2023: one model, one grant,
one human behind it.

It is not the shape institutions now deploy. An orchestrator spawns sub-agents. A
sub-agent calls a tool server it did not write. A faculty system asks a registry
agent to confirm a record, and that agent asks a third. Authority travels, and it
travels through hops that were each individually reasonable.

The failures this produces are ordinary:

* **The confused deputy.** A narrowly-granted agent asks a broadly-granted
  sibling for help, and the broad grant is what executes. Unchanged since Hardy
  named it in 1988, now reachable through a polite request in natural language.
* **Scope re-amplification.** A hop delegates onward more than it holds, because
  each hop validates only what it was asked for.
* **Authority laundering.** A principal appears twice in a chain and regains,
  through the loop, a scope it never held directly.
* **Orphaned delegation.** A delegation outlives the grant it descends from,
  because the hop that issued it never rechecked its own ancestor.

A perfectly aligned model at every hop produces all four.

### Method

Authority is modelled as a scope over five independent axes — tools, operations,
resources, a ceiling on action class, and egress — ordered by a `covers` relation
that is deliberately conservative in both directions: an unbounded scope covers
anything, and nothing bounded covers an unbounded one, so no hop widens a grant
by claiming breadth.

The rule is one sentence:

> **No principal may pass on authority it does not itself hold, and no chain may
> end with more authority than its root was granted.**

Authority under delegation is therefore *monotonically non-increasing*. It may
narrow at every hop and may never widen at any, which makes a chain checkable in
one pass without trusting any hop's account of itself. What a chain confers at
its leaf is the **intersection** of every grant along it — not the last hop's
declaration, so a hop that declares a wide scope gains nothing if an ancestor was
narrow.

Nine invariants, each with a stable denial code and each independently ablatable:

| | Invariant | Denial code |
|---|---|---|
| D1 | Attenuation — every hop's scope is covered by its delegator's | `SCOPE_NOT_ATTENUATED` |
| D2 | Rooted authority — the chain descends from an institutional grant naming an accountable owner | `CHAIN_NOT_ROOTED` |
| D3 | Depth bound — no chain longer than the declared maximum | `DEPTH_EXCEEDED` |
| D4 | Temporal containment — no delegation outlives its delegator's | `DELEGATION_OUTLIVES_DELEGATOR` |
| D5 | Acyclicity — no principal appears twice | `CHAIN_CYCLE` |
| D6 | Provenance — every hop signed by its delegator under a trusted key | `DELEGATION_SIGNATURE_INVALID` |
| D7 | Non-delegable consequence — a machine may not pass on authority a human had to grant | `CONSEQUENCE_NOT_DELEGABLE` |
| D8a | Holder binding — a chain authorises the principal it names and no other | `REQUESTER_NOT_CHAIN_LEAF` |
| D8b | Beneficiary attenuation — work done *for* another principal runs under that principal's authority | `OUT_OF_EFFECTIVE_SCOPE` |

D3 deserves a note, because depth is not a security property by itself. It is an
*accountability* property: past some length nobody can answer the student's
question of who decided.

### Three architectures

Identical chains go to three architectures, reported on one scale.

**Arm A — unguarded.** The leaf presents the scope it says it holds and the
executor uses it. Not a strawman: this is the default behaviour of every
sub-agent framework that passes a context object down and trusts what comes back
up. The chain is present in the logs and absent from the decision.

**Arm B — caller-checked.** Each hop validates its *immediate* delegator. This is
what a careful engineer builds after thinking about the problem for an afternoon,
and it is genuinely a control — it stops outright re-amplification at the hop
where it happens, and it catches a hop whose own signature fails.

What it cannot do is see the chain. With no view of the root it cannot tell that
the authority lapsed two hops up, that the principal it is talking to already
appears earlier, or that the chain descends from no institutional grant at all.

**Arm C — chain verification.** Conferred authority is recomputed from the root
grant down, on every call.

### Results

| | Arm A unguarded | Arm B caller-checked | Arm C this architecture |
|---|---|---|---|
| Hostile chains contained | 0 / 10 | 2 / 10 | **10 / 10** |
| Benign two-hop chain completes | yes | yes | **yes** |

All nine invariants are load-bearing: each removed in turn, each restoring its
harm. Bounded enumeration over the declared chain space — depth, attenuation,
expiry, rootedness, signature, holder binding, cycles — explores **768
configurations with zero violations** against five invariants.

The benign row matters as much as the hostile ones. A delegation control that
refuses every chain contains everything and has removed the capability rather
than governed it.

### The finding

Arm B is the result worth carrying into the room. It is a real control,
correctly implemented, doing exactly what it was designed to do — and it contains
two of ten risk classes. Every hop is locally correct and the composition is
wrong.

**Local validation at every hop is not equivalent to verifying the chain**, and
the gap between them is precisely the set of defects nobody can find by reviewing
one service. An institution auditing a multi-agent deployment service by service
will find each one correct.

### A defect in our own work

The first run of this suite **admitted the confused deputy**, and the defect was
in the checker rather than a fixture.

Every invariant held. The chain presented was authentic, rooted, attenuated,
unexpired, acyclic, and within depth. It simply was not the *requester's* chain:
nothing bound the chain to the principal presenting it, so any holder of a valid
chain could present it. An authority object bound to nobody is a bearer token,
and a bearer token is the thing this architecture exists to refuse.

D8 exists because of that run. The regression test is
`test_a_chain_is_bound_to_the_principal_it_names`.

The honest version of the confused deputy came with it. A broad sibling acting
for a narrow one, *declaring it honestly*, is legitimate orchestration and must
work — so the fix is not refusal but attenuation: the effective authority becomes
the intersection of the actor's chain and the beneficiary's. Doing a job for
someone does not lend them your grant. An actor that will not name the
beneficiary is refused rather than resolved in its own favour.

### Limits

* Bounds authority under composition, never the competence or intent of any hop.
  A fully attenuated chain can carry a substantively wrong action; that class is
  Part II's problem.
* Bounded enumeration, not a proof. Unbounded principal identifiers, concurrent
  delegation, **revocation propagation to already-issued descendants**, and key
  compromise at an intermediate hop are outside the bounds and named as such.
* No real multi-agent deployment was observed. These are constructed chains.
* Arm B is our construction of a plausible careful implementation, not a survey
  of deployed ones.
* Signatures are HMAC over a demonstration key. Production requires real key
  custody, which is `XC-2` and is not solved here.

### Reproduce

```bash
fssaira delegation                    # three arms, nine ablations, 768 states
pytest tests/test_delegation.py -q
```

---

## Part II — Assisted review

### Research question

The oversight contribution establishes that human review is finite, that the
ceiling is computable, and that a queue beyond it turns oversight into a
signature service while every test stays green. That argument models an
**unaided** reader. What happens when the reviewer has a model assistant — and
what decides whether the answer is benign?

### Why this is not a straw problem

An institution whose queue exceeds its roster will give reviewers an assistant,
and it should. In our trial, assistance completes **5x** the legitimate work of
the unaided arm, which contains every merit failure by deferring 32 of 40 cases
to manual review. Assistance is not the mistake. It is the correct response to a
real constraint, and it works.

### The mechanism

The deliberation floor is calibrated to unaided human reading time. An assisted
reviewer legitimately decides faster, so an institution deploying assistance
*must* lower the floor or it throttles reviewers who are doing their jobs.
Lowering it is correct.

But the floor was never really measuring seconds. It was a proxy for **a second
mind independently reaching the same conclusion**, and whether that proxy
survives assistance depends on a property nobody currently declares.

If the review assistant is the same model family, reading the same evidence
packet, with the same framing, it is not a second mind. It is the proposer's
reasoning arriving a second time wearing a reviewer's badge. On exactly the cases
where the proposer was wrong — the applicant is ineligible, the evidence does not
support the recommendation, the case needed a conversation — the assistant is
wrong the same way, for the same reason, and it is fluent and confident about it.
The reviewer ratifies.

This is correlated failure between the proposer and the checker: an old result in
dependable systems, and a new one here only because the two components are now
the same technology.

### Method: independence as a declarable property

Three properties, each answerable by an institution about its own deployment
without measuring anything, and each requirable in writing by a procurement
process:

| Property | What it means | Why it matters |
|---|---|---|
| **Different model** | a different family or provider from the proposer | two instances of the same model with different prompts do not qualify; the correlated error is in the weights, not the prompt |
| **Different evidence path** | the assistant reads the authoritative record, not the packet the proposing agent assembled | an assistant handed the proposer's selection inherits the proposer's selection errors, which are the ones that matter |
| **Adversarial posture** | tasked with finding grounds to refuse and surfacing what is missing, not with summarising | a summariser is optimised to agree with its input; its failure mode on a wrong proposal is a fluent summary of a wrong proposal |

The floor a deployment may set is a function of what it declared. Throughput is
bought with independence and not otherwise. The enforcement point is a
**configuration gate**: a deployment declaring a dependent assistant and a
lowered floor does not start, refused with
`FLOOR_BELOW_DECLARED_INDEPENDENCE` naming the floor it would have to raise to.

The gate binds at configuration time rather than at runtime, and that is not a
shortcut. At runtime the two deployments are indistinguishable — same reviewer
identity, same interval, same signature, same evidence. The difference exists
only in the declaration, so the declaration is where it has to be enforced.

### Results

Four deployments, one queue of 40 arrivals, one reviewer.

| Arm | Floor | Independence | Merit failures | Benign completed | Deferred |
|---|---|---|---|---|---|
| Unaided, full floor | 45s | 3/3 | **0** | 7 | 32 |
| Assisted, dependent, lowered floor | 10s | 0/3 | **5** | 35 | 0 |
| Assisted, independent, lowered floor | 10s | 3/3 | **1** | 35 | 0 |
| Assisted, dependent, gate enabled | — | 0/3 | *deployment refused at configuration* | | |

In the harmful arm the evidence chain is intact, the reviewer is inside quota,
every approval clears the configured floor, and no oversight refusal fires. An
operator watching the dashboard sees a well-run deployment. **There is no runtime
signal to alert on.**

### Two findings, and the second is the important one

**First:** a dependent assistant reintroduces the merit-failure class that the
oversight control was built to catch, while every mechanism keeps passing.

**Second, and less comfortable:** the independent arm reaches **1, not 0**.

That is the result, not a tuning failure. Independence multiplies a reviewer's
effective attention; it does not make attention unbounded. Past the extended
budget, the unaided failure mode returns unchanged. An institution that buys an
assistant has bought **a larger ceiling to compute, not permission to stop
computing one** — and an institution that treats assistance as removing the
oversight question has made the original error at one level up.

### Limits

* The proposer/assistant error correlation is a **declared parameter**, exactly
  like the reviewer degradation curve. No model was evaluated, no assistant was
  measured, and no rate is claimed for any named system. Measuring real
  correlation is open work and is the number that decides how much throughput
  assistance can safely buy.
* The floor multipliers encode a judgement about what independence is worth. An
  institution that disagrees should set its own and publish them.
* The reviewer degradation curve remains declared, not observed. No human was
  observed in any part of this work.
* One reviewer and one queue. This models a mechanism, not an institution.

### Reproduce

```bash
fssaira assisted-review profiles/student_support.yaml
pytest tests/test_assisted_review.py -q
```

---

## What both parts argue for the panel

Publish your oversight ceiling before your automation roadmap, and recompute it
when reviewers get an assistant. Declare the independence of anything that
reviews a model's work. Verify chains rather than hops.

None of that requires a budget, a vendor, or a new standard. It requires an
institution to write down what it has actually delegated and to whom, which is
the same diagnostic the seven-field control contract applies to everything else —
and which remains, on the evidence of our own contract, the part most likely to
have been skipped.

## Artifact provenance

Every figure here is generated by `scripts/generate_results.py` into
`evaluation/results/` and checked against this document and the extended abstract
by `tests/test_paper_alignment.py`. If prose and code disagree, the build fails.
