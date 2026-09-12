# Panel script — UNU Macau AI Conference 2026

**Session:** Agentic AI in the Loop — From Autonomous Tools to Shared Capacity
**Conference:** AI × Education: AI for Learning, Learning for AI · 25–26 November 2026 · Macau SAR
**Deck:** [`slides.html`](slides.html) — arrow keys or click to advance, `n` for these notes on screen, `g` for the slide grid, `⌘P` for a PDF.

A panel opener is not a conference talk. The room has three or four other people
who also have something to say, and the moderator is watching the clock. The deck
runs **23 slides in about fourteen minutes**, with two backup slides that appear
only if someone asks.

Four paths are built in. Pick one before you walk on stage. **Every one of them
ends on slide 23**, because a talk that stops on the limits slide has ended on
the weakest thing you had to say.

| You have | Run slides | Cut |
|---|---|---|
| **14 minutes** | 1–23 | nothing |
| **10 minutes** | 1, 2, 4, 5, 6, 7, 8, 12, 14, 15, 18, 19, 20, 21, 22, 23 | sovereignty (3), method (9), finding (10), atomicity (11), harms (13), second domain (16), corpus (17) — fold 16 and 17 into one sentence each on 18 |
| **8 minutes** | 1, 2, 4, 5, 7, 12, 14, 15, 18, 19, 20, 23 | the above, plus privilege invariance (6), counterfactual (8), theme (21), the ask (22) |
| **5 minutes** | 1, 2, 5, 14, 15, 19, 20, 23 | everything but the rule, the person, the contract, the oversight argument, the limits, who this is for, and the close |

**Three slides are never cut.** Slide 19, the limits: in a UN room the credibility
of everything before it depends on those being stated by you rather than
extracted from you. Slide 20, who this is for: without it this is a talk
about software. And slide 23, the close: it is the only slide that hands the room
the sentence you want repeated after you sit down.

Slides 14 and 15 are the oversight argument, and they are the reason this
submission is on a panel rather than in a poster session. Cut the architecture
before you cut them.

The arc is deliberate. It opens on a person who cannot find out why a decision
was made about her, spends the middle earning the right to be believed, and
returns to her before the close. If you find yourself running long, cut from the
middle — never from either end.

---

## Timing

| Time | Slide | The one thing this slide has to do |
|---|---|---|
| 0:00 | 1 · The rule | Say the sentence. Then stop for a beat. |
| 0:40 | 2 · The stake | Put **her** in the room. Three questions she is entitled to ask. |
| 1:25 | 3 · Sovereignty | Reframe sovereignty as capabilities, not location. |
| 2:00 | 4 · Architecture | The only diagram. Point at three things, then stop. |
| 2:40 | 5 · The contract | Show a filled-in contract, never an empty template. |
| 3:25 | 6 · Privilege invariance | The subtle leak most agent frameworks still have. |
| 4:00 | 7 · Demonstration | A governance rule behaving as observable code. |
| 4:40 | 8 · Counterfactual | Make the containment number believable. |
| 5:20 | 9 · Three questions | The research gap: demonstration, not design guidance. |
| 6:00 | 10 · The finding | The method found a defect in our own work. |
| 6:40 | 11 · Atomicity | A failure mode removed, and the residual named. |
| 7:15 | 12 · The experiment | Compared to what? Three architectures, same attacks. |
| 7:55 | 13 · Harms delivered | Count what reached the asset, not what was refused. |
| 8:25 | 14 · The hard part | **The slide they will remember.** Oversight is finite. Slow down. |
| 9:00 | 15 · Oversight measured | Two numbers: 2,640/day for this roster, and 4 → 0. |
| 9:40 | 16 · A second domain | Generalization, and the defect it found in us. |
| 10:15 | 17 · The corpus | The invitation. Say the ask: contribute one attack. |
| 10:50 | 18 · Evidence | Numbers with denominators. |
| 11:25 | 19 · Limits | **Never cut this.** |
| 12:00 | 20 · Who this is for | **Never cut this.** Return to her. |
| 12:35 | 21 · Both directions | Earn the panel slot on the conference theme. |
| 13:05 | 22 · The ask | Something the room can do — hand them the worksheet. |
| 13:35 | 23 · Close | The rule, then the stake. Then stop. |
| — | 24 · Backup | The five domains, if the panel turns technical. |
| — | 25 · Backup | The interface inventory, for "but you have a diode". |

**If you are given ten minutes rather than fourteen,** take the ten-minute path
above: cut 3, 9, 10, 11 and 13, and fold the second domain (16) and the corpus
(17) into one sentence each on slide 18. Do not cut 14 or 15: the oversight
argument is the reason this submission is on the panel rather than in a poster
session. Do not cut 19, 20 or 23 under any circumstances.

---

## Lines worth having ready

**The opening.** "A model may propose an action. It cannot manufacture the
authority to execute it." Read it once, slowly, and let the room sit with it
before you start explaining. Everything after is about making that testable
rather than asserted.

**Her three questions (slide 2).** "Who decided this, and were they allowed to.
What did they see when they decided. How do I contest it." Then: *in most
agentic systems shipping today there is no answer to any of the three — not
because anyone intended that, but because nothing was built to produce one.*
This is the moral core of the talk. Everything technical exists to make those
three answerable.

**The line that makes the humanitarian claim honest (slide 20).** "A perfectly
governed agent enforcing an unjust policy produces well-documented injustice,
faster. This makes harm attributable. It does not make a rule fair." Say it out
loud. An advocate in the room will otherwise raise it for you, and owning it is
what makes everything else credible.

**The close.** "We are about to hand consequential decisions about people to
systems that cannot yet say who decided, what they saw, or how to contest it.
That is a choice, not a trajectory — and it is still open." Slowly. Then stop;
do not add a thank-you slide.

**On sovereignty.** "Sovereignty is not a postcode." Six capabilities: govern
access, deploy and replace the model, hold the keys, change the policy, produce
evidence, and leave. The sixth usually gets a reaction — exit is the capability
procurement forgets to buy.

**On the contract.** "A capability whose seven fields cannot be filled is a
capability nobody is ready to automate." If the panel drifts toward procurement,
come back here: the seven fields work as an RFP section with no modification.

**On privilege invariance.** "The proposer must not be allowed to set its own
review level." This is the line for the sceptical engineer in row three.

**During the demo.** With `APPROVAL_PAYLOAD_MISMATCH` on screen: "That is a
governance rule behaving as observable code."

**On the finding (slide 8).** "Our own attack suite was measuring less than it
claimed, and a green test run would never have told us." This is the strongest
credibility move available. Do not skip it to save time.

**On the numbers.** "A system that denies everything scores perfectly on
containment and is useless." Then the false-denial rate. In a policy-heavy room,
lead with this rather than the containment figure.

**On reproduction.** "The whole suite runs on a disconnected laptop in under two
seconds, so a second institution can check these numbers rather than trust them."
That sentence is the capacity-building argument in one line.

**Handing back to the moderator.** "I would rather be asked which of our limits
matters most in your institution than which of our results is largest."

---

## The demonstration

Rehearse it, then assume it will fail. Slide 6 stands on its own if the room's
network does not.

```bash
# Terminal, large font, one window, no editor visible.
fssaira evaluate profiles/student_support.yaml   # ~0.02s, fully offline
fssaira verify   profiles/student_support.yaml   # 240 states, 0 violations
```

For the console (browser, one tab, pre-warmed):

1. **Actions** tab. Register `S-104`, propose the transition, approve as the officer.
2. Tick **"Alter the destination state after review"**, propose again, execute.
   The oxide-red `APPROVAL_PAYLOAD_MISMATCH` is the moment. Pause on it.
3. **Evidence** tab. Show the hash chain, then the two records the successful
   execution left — intent and outcome.
4. If there is time, **Intelligence** tab, load the injection specimen, and show
   the catalogue reclassifying a model's self-declared "reversible".

Pre-flight: `docker compose --env-file deploy/.env -f deploy/compose.yaml up -d`,
then open `http://localhost:8088`, run one full cycle, and **leave the tab
open**. Do not demo from a cold start.

### The takeaway (slide 19)

Have `docs/worksheet/` open in a third tab. If the moderator allows it, invite
the room to fill in one capability *during* the panel — it takes about fifteen
minutes, runs entirely in their browser, and emits configuration they can run.
A room that leaves having written one control contract has adopted something; a
room that leaves having heard about one has not.

The weak-draft example is worth thirty seconds if there is time. It is the same
worksheet filled in the way most organisations would fill it in today —
"the IT team" as owner, "the system prompt instructs the model" as enforcement
point — and it scores 0 of 7. That lands harder than any argument.

---

## Questions you should expect

Twenty, in the order they are most likely to come. Each has a short answer, a
deeper one if pressed, and the thing in the repository that backs it.

The first four are new, and the first one is the likeliest question in the room.

---

**0 · "You have just built a system that refuses more work. How is that a win?"**
*Expect this first, and agree with the premise immediately.* Yes — under load the
control defers actions to manual review, and in our trial that was 32 of them.
That deferral count is the finding, not a defect. It is the gap between what the
institution is sending and the review capacity it declared, made arithmetic
instead of invisible. An institution that dislikes the number was already over
capacity; it simply had no instrument that said so, because every digest still
bound and every log still said a human approved it.
*Deeper:* the control is silent when the institution is staffed for the work —
`test_a_queue_inside_capacity_defers_nothing` asserts exactly that, so this is not
a throttle dressed up as a safeguard.
*Backed by:* `fssaira oversight`, slides 14–15.

**0a · "Did you actually measure any reviewers?"**
*Answer this before anyone has to ask it, on the slide.* No. Not one. The
degradation curve is a declared parameter an institution supplies, and it is
labelled as such in the module, the CLI output, the generated results, and the
assurance ledger. What we demonstrate is that given any curve an institution will
declare, its ceiling is computable and the control binds at it. Observing real
reviewers needs a study with human subjects, not more code, and `ASSURANCE.md` §7
names it as the largest open gap between this and a field claim.
*If pressed on why it still counts:* the arithmetic does not depend on the curve.
A roster, a deliberation floor, and available hours give you a ceiling today, with
numbers you already have.

**0b · "Two domains is not generalization."**
Correct, and we say so. Two domains, both authored here, show the method travels
off the shape it was designed for — not that it travels everywhere. What makes it
worth reporting is what it cost us: the second domain failed on its first run and
exposed a mandatory schema field that did nothing at runtime, unreachable with one
domain. That is evidence *against* single-domain results, including the rest of
ours.
*Backed by:* `fssaira verify profiles/academic_record_correction.yaml`, slide 16.

**0c · "Every attack in your evaluation is one you wrote."**
Also correct, and it is the standing weakness of the whole evidence base. It is
why the corpus exists and why the tool prints an externally-contributed count of
zero rather than hiding it. The mechanism is deliberately cheap to use: seven
fields of YAML, no contributor code, nothing an institution would need to clear.
*Turn it into the ask:* if you think we have missed an attack, that is a pull
request, and the corpus already found a defect in our own measurement on its
first run.
*Backed by:* `fssaira challenge`, slide 17.

**1 · "Isn't this just a testing framework?"**
No. A test suite proves the attacks I imagined are contained. Two of our three
artifacts answer questions I structurally cannot answer by writing more tests:
what about the combination nobody imagined, and does it still hold after you
replace my components with yours.
*Deeper:* the bounded model checker found a defect in our own suite — four
adversarial variants were being caught one check early, leaving the expiry,
audience, and role checks unexercised. A green test run would never have said so.
*Backed by:* `fssaira verify`, `fssaira conformance`, slide 10.

**2 · "Compared to what? Any locked door stops burglars."**
That is the right question, and it is why the comparison exists. The same seven
attacks go to three architectures: unguarded, prompt-guarded, and this one. The
prompt-guarded arm is deliberately fair — an allowlist is a real control and it
stops two of seven — and it still lets eight harmful actions through.
*Backed by:* `python scripts/demo.py --act 6`, slides 12–13.

**3 · "Your baseline is a strawman."**
Push back politely and concretely. Arm B has a safety system prompt *and* a
per-agent tool allowlist, which is what most deployed agents have. It contains
29% of attacks, not 0%. If it were a strawman it would contain nothing.
*Deeper:* we also assert this in a test — `test_the_baseline_is_not_a_strawman`
fails the build if Arm B stops nothing.

**4 · "What about prompt injection?"**
We strip mechanically recognisable active content and we explicitly do not rely
on it. The load-bearing controls are downstream: retrieved text is never promoted
to an instruction, egress is denied by default, and a consequential action needs
an approval bound to one exact proposal. We claim no detection rate, because we
have not measured one for a named model.
*Deeper:* every containment figure is measured with the model assumed already
compromised — injection succeeding is the premise, not the failure.

**5 · "Has this been deployed?"**
No. No institutional deployment, no independent audit, no penetration test, no
certification. Slide 19 says so. What we offer is a method and an implementation
whose results reproduce offline in under two seconds.

**6 · "Does human approval actually help, or is it rubber-stamping?"**
Honestly: we have not measured reviewer accuracy or workload, and it is on the
not-yet-evidenced list. What we can say is that an approval binds to one exact
proposal, so a reviewer who approves a specific change cannot have that approval
reused for a different one. Whether they read carefully is a human-factors
question we have not studied, and I would rather say that than imply we have.
*Backed by:* `docs/RESPONSIBLE_AI.md` §4, which marks this row **open**.

**7 · "You have a data diode, so it's secure?"**
A diode governs exactly one link. Slide 25 is the interface inventory — the
administrative shell, telemetry export, backup, model updates, removable media.
Until that list is complete with a named control and owner per line, the
directionality claim is about a link nobody attacks.

**8 · "Why not a commercial model?"**
You can — one line of configuration points it at any OpenAI-compatible endpoint.
What changes is the claim: the deployment records a sovereignty warning saying
prompts and retrieved evidence leave the boundary, and the data-residency claim
no longer holds. The architecture does not stop you; it stops you doing it
silently.

**9 · "What does this cost to run?"**
The governance layer is close to free: the full suite, the model check, and the
evaluation run offline in under two seconds with no GPU. Inference cost is a
property of whichever model you choose and we do not measure it. We make no
energy claim in either direction — constraining an agent's authority does not by
itself reduce the cost of running it.

**10 · "Will this scale beyond a toy?"**
The durability profile scales in three steps, and the deployment reports which
one is in force: in-memory for teaching, Redis for durable multi-process, and a
single transaction on PostgreSQL where the register and the evidence ledger share
a database. SQLite is a first-class transactional profile, not a toy — it is what
proves the atomicity property in CI.
*Limit:* concurrency and distributed failure modes are not evaluated. The model
checker is single-threaded and says so in its own bounds field.

**11 · "What about privacy and data protection?"**
Records never leave by default: egress is denied, the model is local, and the
metrics exporter publishes counters only — never payloads or identifiers. The
evidence ledger is the exception worth naming, because it deliberately retains
decision records; retention must outlive the appeal window, which makes it a
governance setting rather than an operational default.

**12 · "Could this entrench bias rather than reduce it?"**
Yes, and that is the risk I would want a policy audience to hold onto. A
perfectly governed agent enforcing an unjust policy produces well-documented
injustice, faster. Our contribution is that the injustice becomes
*attributable* — a named person authorized it, against a recorded evidence
version. That is real and it is modest. It does not make the rule fair.
*Backed by:* `docs/IMPACT.md`, which marks fairness **out of scope** rather than
claiming it.

**13 · "Who actually benefits?"**
The person the decision is about, first: they get a decision that cannot happen
without a named authorizer, and a record the operator cannot silently edit. Then
the caseworker, who gets assistance that cannot decide. Then the institution,
which can replace a vendor without losing its assurance argument.
*Backed by:* `docs/IMPACT.md`, with every line labelled demonstrated, reasoned,
hypothesis, or out of scope.

**14 · "What would it take to run this at my institution?"**
One bounded workflow, a named service owner, and a manual fallback that person
owns. The worksheet does the first capability in about fifteen minutes; the
playbook is 30/60/90 days to a pilot on synthetic data. Do not start with the
workflow that matters most.

**15 · "How does this relate to the EU AI Act, or our national rules?"**
Deliberately, it claims compliance with none of them. It produces the artifacts a
compliance conversation needs — a named enforcement point, an executable failure
test, an evidence record, and an accountable owner per capability. Mapping those
to an instrument is work your counsel does, and I would rather supply evidence
than assert a conclusion.

**16 · "What is genuinely novel here?"**
Three things. Bounded model checking of a governance profile's whole declared
authority space rather than a hand-picked attack list. An authority coverage
figure computed by ablation, so a decorative control is visible as decorative.
And a portable conformance suite, so replacing a component does not quietly void
the assurance argument. The individual controls are not new; making the argument
survive substitution is.

**If you are asked something you have not measured** — reviewer accuracy, field
injection rates, cost, fairness, energy — say so, name where it is written down,
and offer the experiment you would run. In this room, that answer is worth more
than an estimate.

## If the panel turns to policy

Three points worth making, in order of how often they land:

1. **Publish three things per capability** — a named boundary, an executable
   failure test, and a recovery owner. This is a policy ask that an institution
   can act on without buying anything.
2. **Demand denominators.** Any containment figure without a benign-task
   completion rate beside it is unfalsifiable. This applies to vendors and to
   researchers, including us.
3. **Shared tests, not shared infrastructure.** Institutions cannot pool their
   student records and mostly cannot pool their infrastructure. They can pool
   failure cases and conformance results, and that is a digital public good in
   the sense the Global Digital Compact means.

---

## Housekeeping

- Deck renders in the viewer's light or dark theme; check the room's projector
  before deciding which to force.
- `⌘P` produces a one-slide-per-page PDF for the conference organisers.
- The deck's figures are generated by `scripts/generate_results.py` and checked
  by `tests/test_paper_alignment.py`. If a number on a slide is wrong, the build
  is failing — fix the number, not the slide.
