# Panel script — UNU Macau AI Conference 2026

**Session:** Agentic AI in the Loop — From Autonomous Tools to Shared Capacity
**Conference:** AI × Education: AI for Learning, Learning for AI · 25–26 November 2026 · Macau SAR
**Deck:** [`slides.html`](slides.html) — arrow keys or click to advance, `n` for these notes on screen, `g` for the slide grid, `⌘P` for a PDF.

A panel opener is not a conference talk. The room has three or four other people
who also have something to say, and the moderator is watching the clock. The
deck runs **16 slides in about ten minutes**, with two backup slides that only
appear if someone asks.

Three paths are built in. Pick one before you walk on stage.

| You have | Run slides | Drop |
|---|---|---|
| **10 minutes** | 1–16 | nothing |
| **7 minutes** | 1, 2, 4, 5, 6, 7, 10, 12, 13, 15, 16 | sovereignty (3), counterfactual (8), method (9), atomicity (11), theme (14) |
| **5 minutes** | 1, 2, 5, 7, 12, 13, 15, 16 | everything else — keep the contract, the demo, the numbers, the limits, the ask |

**Slide 13 is never dropped.** In a UN room, the credibility of everything before
it depends on the limits being stated by you rather than extracted from you.

---

## Timing

| Time | Slide | The one thing this slide has to do |
|---|---|---|
| 0:00 | 1 · The rule | Say the sentence. Then stop for a beat. |
| 0:35 | 2 · The question | Put a real workflow in the room before any architecture. |
| 1:15 | 3 · Sovereignty | Reframe sovereignty as capabilities, not location. |
| 1:50 | 4 · Architecture | The only diagram. Point at three things, then stop. |
| 2:30 | 5 · The contract | Show a filled-in contract, never an empty template. |
| 3:15 | 6 · Privilege invariance | The subtle leak most agent frameworks still have. |
| 3:50 | 7 · Demonstration | A governance rule behaving as observable code. |
| 4:10 | 8 · Counterfactual | Make the containment number believable. |
| 4:50 | 9 · Three questions | State the research gap: demonstration, not design guidance. |
| 5:30 | 10 · The finding | The method found a defect in our own work. |
| 6:10 | 11 · Atomicity | A failure mode removed, and the residual named. |
| 6:50 | 12 · Evidence | Numbers with denominators. |
| 7:30 | 13 · Limits | **Never cut this.** |
| 8:05 | 14 · Both directions | Earn the panel slot on the conference theme. |
| 8:40 | 15 · The ask | Something the room can do — hand them the worksheet. |
| 9:15 | 16 · Close | Return to the opening sentence. |
| — | 17 · Backup | The five domains in detail, if the panel turns technical. |
| — | 18 · Backup | The interface inventory, for “but you have a diode”. |

---

## Lines worth having ready

**The opening.** "A model may propose an action. It cannot manufacture the
authority to execute it." Read it once, slowly, and let the room sit with it
before you start explaining. Everything after is about making that testable
rather than asserted.

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

### The takeaway (slide 15)

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

**"Isn't this just a testing framework?"**
No. A test suite proves the attacks I imagined are contained. Two of our three
artifacts answer questions I structurally cannot answer by writing more tests:
what about the combination nobody imagined, and does it still hold after you
replace my components with yours.

**"You have a data diode, so the system is secure?"**
A diode governs exactly one link. Slide 16 is the interface inventory — the
administrative shell, telemetry export, backup, model updates, removable media.
Until that list is complete with a named control and owner for each line, the
directionality claim is about a link nobody attacks.

**"What about prompt injection?"**
We strip mechanically recognisable active content and we do not rely on it. The
load-bearing controls are downstream: retrieved text is never promoted to an
instruction, egress is denied by default, and a consequential action needs an
approval bound to one exact proposal. We do not claim a detection rate, because
we have not measured one for a named model.

**"Has this been deployed?"**
No. No institutional deployment, no independent audit, no penetration test, no
certification. Slide 11 says so. What we offer is a method and a reference
implementation whose results reproduce offline.

**"Does the human approval actually help, or is it rubber-stamping?"**
An honest answer: we have not measured reviewer accuracy or workload, and that
is on the not-yet-evidenced list. What we can say is that the approval binds to
one exact proposal, so a reviewer who approves a specific change cannot have that
approval reused for a different one. Whether the reviewer reads carefully is a
human-factors question we have not studied, and I would rather say that than
imply we have.

**"Why not a commercial model?"**
You can — the backend is pluggable, and one line of configuration points it at
any OpenAI-compatible endpoint. What changes is the claim: the deployment then
records a sovereignty warning saying prompts and retrieved evidence leave the
boundary, and the data-residency claim no longer holds. The architecture does
not stop you; it stops you doing it silently.

**"What would it take to run this at my institution?"**
One bounded workflow, a named service owner, and a manual fallback that person
owns. `fssaira init` scaffolds the profile, the contract, and a deliberately
failing test you replace with the attack you actually fear. Two to four weeks
for a pilot on synthetic data. Do not start with the workflow that matters most.

**"How does this relate to the EU AI Act / national AI rules?"**
Deliberately, it does not claim compliance with any of them. It produces the
artifacts a compliance conversation needs — a named enforcement point, an
executable failure test, an evidence record, and an accountable owner per
capability. Mapping those to a specific instrument is work an institution's
counsel does, and we would rather supply the evidence than assert the conclusion.

**"What is genuinely novel here?"**
Three things. Bounded model checking of a governance profile's whole declared
authority space rather than a hand-picked attack list. An authority coverage
figure computed by ablation, so a control that is decorative is visible as
decorative. And a portable conformance suite, so replacing a component does not
quietly void the assurance argument. The individual controls are not new; making
the argument survive substitution is.

---

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
