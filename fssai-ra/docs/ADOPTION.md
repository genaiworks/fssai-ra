# Adoption playbook

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Continue the policy route → [`OPERATIONS.md`](OPERATIONS.md)

A 90-day path from "we read the paper" to "we have one governed capability with
evidence we generated ourselves."

This is written for the person who has to make it happen inside an institution,
not for the person who decides it should. It assumes no budget, no new
infrastructure, and no authority to change how anyone else works.

**The first rule of this playbook: do not start with the workflow that matters
most.** Start with the one where a wrong decision is annoying rather than
harmful, and where you already know who owns it. You are building the capability
to govern automation, not automating the thing.

---

## Before day 1 — the fifteen-minute version

Do this before asking anyone for anything.

1. Open [`docs/worksheet/`](worksheet/) (or the hosted copy) and fill in **one**
   capability. Not a system, not a strategy — one operation on one record.
2. Note which of the seven fields you could not fill.

That list is your actual finding. In most organisations the field that fails is
**accountable owner** or **enforcement point**, and both failures mean the same
thing: the control being claimed does not exist yet. You now have something
specific to say in a meeting, which is more than a maturity model will give you.

3. Open the [oversight capacity calculator](oversight/) and answer five
   questions you already know the answers to: how many people may approve this
   class of action, how many hours a day they actually have for it, how long a
   careful reading takes, the most you would let one person approve in an hour,
   and how many of these actions a day the queue sends.

That produces a second finding, and it is usually the more uncomfortable one.
Every governed-agent design routes consequential actions to a named human; very
few say what happens when there are more actions than the humans can read. If
your demand exceeds your ceiling, four answers are honest — hire, narrow what
counts as consequential, accept a queue and publish its length, or let those
approvals stop being review. The fourth happens by default if nobody chooses.

The calculator runs offline and sends nothing anywhere, which is deliberate:
finding out that you are over capacity should not require telling anyone.

```bash
pip install "fssaira[dev] @ git+https://github.com/genaiworks/fssai-ra#subdirectory=fssai-ra"
fssaira init my-domain --domain-id my-domain --title "My Domain"
fssaira verify my-domain/profile.yaml
```

---

## Days 1–30 · One capability, on paper, with a name against it

**Goal:** a control contract that a named person has read and agreed to.

| Do | Who | Done when |
|---|---|---|
| Pick the capability. Write the seven fields. | You | The worksheet scores 7 of 7 |
| Find the accountable owner and ask them to confirm | You + that person | They can state, unprompted, what happens when the automation refuses |
| Write the manual fallback with a real turnaround | Service owner | It names working days, not "promptly" |
| Write the failure test as an attempt, not an aspiration | You | Someone else could run it from the text |
| Run `fssaira verify` on the profile | You | 0 violations, and you understand the bounds it states |

**The conversation that matters.** Ask the owner: *"If this refuses at 4pm on a
Friday, what happens to the applicant?"* If there is no answer, the capability is
not ready, and that is a finding worth more than a pilot.

**Common failure at this stage.** Writing seven fields for a capability nobody
has agreed to automate. The contract is not a proposal document; it is a record
of a decision someone has already taken. If no one has taken it, say so.

---

## Days 31–60 · Make it run on synthetic data

**Goal:** the workflow executes end to end, against records that cannot hurt
anyone, with evidence you can show to a sceptic.

```bash
# Core stack: Postgres, Redis, Kafka, control API, import gateway, console.
python scripts/bootstrap_dev_env.py
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d

# Add a local model only when the rest works. It is the least load-bearing part.
docker compose --env-file deploy/.env -f deploy/compose.yaml --profile model up -d
```

| Do | Why |
|---|---|
| Replace every credential in `deploy/.env` | `fssaira doctor` will keep telling you until you do, and it is right |
| Set `FSSAI_DATABASE_URL` | Single-transaction durability; the interrupted-outcome failure mode disappears |
| Run `fssaira conformance --backend sql` | Confirms the properties hold on *your* backend, not the reference one |
| Run the failure test from day 1–30 and watch it fail closed | This is the moment the work becomes real to a sceptic |
| Walk the owner through the Evidence tab of the console | They should be able to point at the record that names them |

**Use synthetic records.** Not anonymised real ones — synthetic. Anonymised data
carries re-identification risk into a pilot that does not need it, and you will
spend the credibility you need later arguing about it now.

**The number to record.** `fssaira evaluate` reports a false-denial rate beside
the containment rate. Both go in the pilot report. A pilot that reports only
containment will be read, correctly, as a pilot that was not measuring usability.

---

## Days 61–90 · Produce evidence, then decide

**Goal:** a written result an independent reader can check, and an explicit
decision about whether to continue.

| Produce | Command | Goes to |
|---|---|---|
| Machine-readable results | `python scripts/generate_results.py` | The pilot report appendix |
| Conformance attestation for your backends | `fssaira conformance --output conformance.json` | Whoever signs off the deployment |
| Interface inventory | `fssaira diode inventory --output interfaces.json`, then **replace it with yours** | Security review |
| Readiness verdict | `fssaira doctor --output readiness.json` | The deployment gate |
| Your own `ASSURANCE.md` | Write it — do not copy ours | The permanent record |

**Write your own assurance file.** The scaffold ships an empty one on purpose.
Our results describe our profile, our fixtures, and our environment. A new domain
inherits the structure and none of the evidence; borrowing results is how a
method decays into a vocabulary.

**Then make an actual decision**, in writing, with one of three outcomes:

- **Continue** — expand to a second capability, same method, new evidence.
- **Stop** — and record why. A capability that failed this process was going to
  fail later and more expensively. This is the playbook working.
- **Continue with a named gap** — the honest middle. Name the gap, name who owns
  closing it, and name the date it gets re-examined.

---

## What to measure, and what not to promise

| Measure | How | Do not claim |
|---|---|---|
| Unauthorized actions completed per attempt | Evaluation report, `unauthorized_mutations` | That zero means the system is secure |
| Benign task completion | Evaluation report, `false_denial_rate` | That a synthetic suite predicts real usability |
| Time to detect a broken evidence chain | Run the verification job on a schedule; time it | That detection is prevention |
| **Oversight ceiling** | `fssaira oversight <profile> --sweep`, or the calculator, with your own roster | That the ceiling is a measurement of your reviewers. It is arithmetic over what *you* declared, and only as honest as the reading time you entered |
| **Demand against that ceiling** | Count consequential actions per day; compare | That deferrals are a defect. They are the gap between demand and declared capacity, and reporting them is the point |
| Approval latency and reviewer effort | Instrument it; we have not | Anything at all — we have not measured this and neither have you, yet |
| Recovery time after a denied action | Time the manual fallback with a real person | That the fallback works because it is documented |

The last row is the one institutions skip. A manual fallback nobody has walked
through is a paragraph, not a service.

---

## Anti-patterns

**"We'll adopt the architecture."** You cannot. You adopt the method for one
capability, then another. An architecture-wide adoption programme has no failure
test and no owner, which are the two things this method is about.

**"We'll add human review, so the volume does not matter."** It is the only thing
that does. Review is the one input in the pipeline that does not scale with the
hardware, and past a reviewer's capacity every mechanism in this repository still
passes its tests while the oversight they feed becomes a signature service. Put
the ceiling in the business case beside the volume forecast, not after the
pilot.

**"We'll set the reading time lower so the numbers work."** Then the ceiling
describes a queue that already stopped being reviewed. The number is only useful
if you would defend it to the person whose case was refused.

**"Let's put the contract in the wiki."** The contract is enforced configuration.
If it lives somewhere that cannot fail a build, it will drift within a quarter.
`fssaira validate-contract` exists so it cannot.

**"The model is fine, we use a good one."** Every containment result in this
repository is measured against a deliberately compromised backend, because the
architecture is not allowed to depend on the model behaving. If your controls
only hold for a well-behaved model, you have no controls.

**"We'll add the human approval later."** The approval step changes the data
model — a proposal is a durable object, an approval binds to its digest, and
execution is idempotent against a request id. Retrofitting it means rewriting
the write path. It is cheaper on day 1 than on day 200.

**"Copy the student-support assurance table and change the nouns."** See above.
This is the one that quietly destroys the method while appearing to adopt it.

---

## Where to ask for help

- [`docs/EXTENDING.md`](EXTENDING.md) — adding a domain
- [`docs/PLATFORM.md`](PLATFORM.md) — the distributed deployment
- [`docs/OPERATIONS.md`](OPERATIONS.md) — failure and recovery procedures
- [`docs/PROCUREMENT.md`](PROCUREMENT.md) — the seven fields as vendor questions
- [`docs/SECURITY.md`](SECURITY.md) — threat model and residual risk
- Issues and discussions: `github.com/genaiworks/fssai-ra`

Sharing a failure case costs you nothing and is worth more to another institution
than a success story. That exchange — tests and failure cases, not student
records — is what capacity building looks like here.
