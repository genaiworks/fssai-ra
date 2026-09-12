# The seven fields as procurement questions, and two more

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Continue the policy route → [`RESPONSIBLE_AI.md`](RESPONSIBLE_AI.md)

The control contract works unmodified as a supplier questionnaire. Below is each
field as a question, with what a strong answer looks like, what a weak answer
looks like, and what the answer tells you when it does not arrive.

This is deliberately usable by someone who is not an engineer. You do not need to
evaluate the supplier's architecture; you need to find out whether they can name
the things a governed capability must have. A supplier who cannot is telling you
something more useful than a demonstration would.

**Scope it to one capability at a time.** "Your AI platform" has no protected
asset and no enforcement point. "The thing that moves a case to officer review"
does.

---

## 1 · Protected asset

> *What is harmed if this capability behaves incorrectly, and whose is it?*

**Strong.** Names the thing and the person. "An applicant's eligibility decision,
and the payment that follows from it in the next cycle."

**Weak.** "Customer data." "The system." "Data integrity." These are categories,
not assets, and they cannot be used to reason about severity.

**If no answer arrives:** nobody has done an impact analysis for this capability.
Everything that follows is being designed without a target.

---

## 2 · Permitted operation

> *What is the narrowest operation this capability may perform? Not what it can do — what it may.*

**Strong.** One operation, on one class of record, in one direction. "May propose
advancing a claim already assigned to it, from evidence-gathering to
caseworker-decision."

**Weak.** Anything containing "any", "all", "manage", "handle", or a list joined
by "and also". More than one operation in this answer usually means more than one
contract, and the supplier has not separated them.

**If no answer arrives:** the capability's scope is whatever the model decides at
runtime. Ask what constrains it, and expect to hear about the prompt — see §4.

---

## 3 · Enforcement point

> *What service verifies the actual operation against current policy, independently of the model's explanation of what it is doing?*

This is the question that separates suppliers.

**Strong.** Names a service that is not the model, describes what it checks
(operation, target, record version, approval, expiry), and can say what happens
when it is unavailable.

**Weak, and common:**

- *"The system prompt instructs the model not to…"* — the thing being checked is
  doing the checking. There is no control here.
- *"We have guardrails."* — ask which guardrail refuses which operation, and what
  it returns when it does.
- *"There's a review process."* — a process that meets is not a service that
  runs. Ask what refuses the call at 3am.
- *"The model is fine-tuned for safety."* — a property of the model, not a
  boundary on its authority.

**If no answer arrives:** the capability has no independent enforcement. Whatever
else the supplier has built, a compromised or mistaken model reaches the real
side effect.

**Follow-up worth asking:** *"If the model's stated reason for an action and the
actual operation disagree, which one does the system act on?"* The only
acceptable answer is the operation.

---

## 4 · Accountable owner

> *Which role in our institution — not yours — answers when this capability causes harm?*

**Strong.** A role one person holds, on our side, who has agreed. The supplier
should be slightly uncomfortable answering this, because the correct answer
transfers accountability to us.

**Weak.** "Our support team." "Shared responsibility." "The customer's IT
department." A team cannot be accountable, and a supplier who claims to own
accountability for our decisions is describing something they cannot deliver.

**If no answer arrives:** this is a blocking finding. Do not proceed to a pilot
with an unowned capability; the pilot will create decisions nobody answers for.

---

## 5 · Failure test

> *Give us the adversarial attempt that must fail, written so our team can run it.*

**Strong.** A concrete attempt with an expected refusal. "Approve the transition,
then change the target identifier before execution; the system returns a denial
and no record changes." Better still: they hand you a script.

**Weak.** "We do penetration testing annually." "It's been red-teamed."
"Monitoring would catch it." Monitoring is not a failure test — a test has an
input and an expected refusal, and can be run on demand.

**If no answer arrives:** the supplier has tested that the system works, not that
it fails safely. Those are different exercises and only one of them is evidence.

**Ask for the ablation too:** *"If we turned this control off, what would we see
differently?"* A supplier who cannot answer has a control whose necessity nobody
has established.

---

## 6 · Evidence artifact

> *What record would let an affected person challenge a decision, and can they get it?*

**Strong.** Names the record's contents — the operation, the approver, the data
version, the timestamp — and says how someone affected obtains it.

**Weak.** "Full audit logging." "Everything is logged." Logs are where evidence
lives; they are not evidence. Ask what the record contains that lets a person
argue, and whether it can be altered by whoever operates the system.

**If no answer arrives:** decisions will be unchallengeable in practice, whatever
the appeal policy says.

**Follow-up:** *"Who can modify or delete a past record, and is that detectable?"*
Tamper-evidence and tamper-prevention are different claims; suppliers routinely
state the second while implementing the first.

---

## 7 · Failure response

> *When the capability is denied or unavailable, what happens to the person waiting, and who does it?*

**Strong.** A named manual path, with a turnaround in working days, owned by a
role that knows it owns it.

**Weak.** "We alert your team." "It retries." Alerting is not a service —
something has to happen to the applicant while the alert is unread. And retrying
an action whose outcome is uncertain is how one decision becomes two.

**If no answer arrives:** the capability is not fail-secure, it is fail-stuck.
Under load or outage, the people it serves are simply not served.

---

# Two questions the seven fields do not ask

The seven fields describe one capability held by one agent and approved by one
human. Both halves of that sentence are now usually false in a real deployment,
and each false half has its own question. Neither requires the supplier to
disclose anything proprietary; both are answerable in writing.

## 8 · Delegated authority

> *Does this agent ask other agents, or other services, to act for it — and when
> it does, whose authority executes?*

**Strong.** The supplier can name the maximum delegation depth, states that a
delegate's authority is the intersection of every grant in the chain rather than
the last one declared, and can say what happens when an intermediate grant
expires or is revoked. Best answer: the executor recomputes conferred authority
from an institutional root grant on every call, and a chain is bound to the
principal presenting it.

**Weak.** "Each service validates its caller." This is a real control and it is
not the same thing. A per-hop check cannot see the root, so a lapsed grant two
hops up, a principal that appears twice in the chain, and a chain that descends
from no institutional grant at all are invisible to it. Ask specifically: *if
agent A's authority expires, does agent C — which A delegated to via B — stop
working?* A supplier who cannot answer has not modelled the chain.

**Also weak.** "Our agents don't delegate." Ask whether the product calls tool
servers, plugins, MCP servers, or any component the supplier did not write. If
it does, it delegates; it just has not called it that.

**If no answer arrives:** authority in this system is a bearer token. Anyone
holding a valid context can present it, and the question *who was allowed to do
this* has no answer that survives more than one hop.

## 9 · Independence of review assistance

> *If a model helps our reviewers decide, is that model independent of the model
> that produced the proposal?*

This is the question to ask if you ask only one of the two. A supplier will often
offer review assistance as a feature — it raises throughput, genuinely and
substantially — and the deliberation time your officers spend will fall
accordingly. That is fine only if the assistant is a second opinion rather than
the same opinion twice.

**Strong.** All three of these, stated in the contract:

| | What to require | Why |
|---|---|---|
| **Different model** | a different family or provider from the proposing model | two instances of the same model with different prompts do not qualify; the correlated error is in the weights, not the prompt |
| **Different evidence path** | the assistant reads the authoritative record, not the packet the proposing agent assembled | an assistant handed the proposer's selection inherits the proposer's selection errors, which are the ones that matter |
| **Adversarial posture** | tasked with finding grounds to refuse and naming what is missing, not with summarising | a summariser is optimised to agree with its input; its failure mode on a wrong proposal is a fluent summary of a wrong proposal |

**Weak.** "The same model, with a reviewer prompt." "It summarises the case for
the officer." Both describe the proposer's reasoning arriving a second time in a
reviewer's badge. On exactly the cases where the proposal was substantively wrong
— ineligible applicant, evidence that does not support the recommendation, a case
that needed a conversation — the assistant is wrong the same way and confident
about it, and your officer ratifies. Every log will say a human approved it.

**The follow-up that matters:** *what deliberation time does your system expect
per case with assistance enabled, and what did it expect without?* If the number
falls and none of the three independence properties hold, the supplier has sold
you throughput and charged your oversight for it.

**If no answer arrives:** treat the assistant as no assistance for the purposes
of review capacity, and keep the unaided review time in your own planning. You
can always relax that later; you cannot recover a year of approvals nobody read.

---

## Scoring the answers

Do not score this as a percentage. Count blocking findings.

| Field | Weak answer is | Missing answer is |
|---|---|---|
| Protected asset | a warning | a warning |
| Permitted operation | a warning | **blocking** |
| Enforcement point | **blocking** | **blocking** |
| Accountable owner | **blocking** | **blocking** |
| Failure test | a warning | **blocking** |
| Evidence artifact | a warning | **blocking** |
| Failure response | a warning | **blocking** |
| Delegated authority | a warning | **blocking** *if the product calls any component the supplier did not write* |
| Review-assistance independence | **blocking** *if assistance is offered and any of the three properties is absent* | **blocking** |

**One blocking finding is enough to defer.** Not to reject — to defer, with the
finding named, until it is closed. Most suppliers can close these; many have
simply never been asked in these terms.

---

## Four questions to ask about the supplier's own evidence

Separate from the seven fields, and worth more than a demonstration:

1. **"What is the denominator?"** Any containment or accuracy figure without a
   corresponding benign-task completion rate is unfalsifiable. A system that
   refuses everything scores perfectly on safety.

2. **"What did you remove to prove that control matters?"** If no control has
   been ablated, none has been shown to be load-bearing.

3. **"What have you not evidenced?"** A supplier with no limits section has
   either not looked or is not telling you. Ask for the list; compare it with
   [`docs/ASSURANCE.md`](ASSURANCE.md) in this repository, which is what such a
   list looks like when someone has actually written one.

4. **"Which of your controls has an executable test, and which has a written
   one?"** The distinction is not pedantic. A control described in a design
   document and bound to nothing that runs disappears the first time someone
   refactors, and nothing goes red. We found eighteen of those in our own
   contract by building a check for exactly this; `fssaira coverage` is what the
   answer looks like when it is measured rather than asserted. A supplier who
   has never separated the two has not been asked before, which is worth knowing
   either way.

---

## Using this with an open-source or in-house build

The questions do not change when the supplier is your own team. They get harder
to avoid, which is the point. Run the worksheet at
[`docs/worksheet/`](worksheet/) against your own capability before you run this
questionnaire against anyone else's.

---

## The question that is not about the software

Every question above asks what the supplier's system does. This one asks what
your institution will have to supply, and no vendor can answer it for you.

> **How many consequential actions per day will this system route to a named
> human for approval, and how many can we actually review?**

Ask for the first number in writing, as a forecast at full rollout rather than at
pilot scale. Work out the second yourself — the
[oversight capacity calculator](oversight/) takes five numbers you already have,
runs offline, and sends nothing anywhere.

If the forecast exceeds your ceiling, the contract needs one of four answers
written into it: more reviewers funded, a narrower definition of what requires
approval, a published service level for the queue, or an explicit acceptance that
approvals above the line are not review. A procurement that records none of them
has chosen the fourth by default.

**A supplier answer that should concern you:** *"the system is designed so that
review is quick."* Quick review is not the goal; sufficient review is. A supplier
who treats approval latency as a performance metric to minimise has told you what
their product optimises, and it is not oversight.

**A supplier answer that should reassure you:** a number, a stated assumption
about how long a reviewer needs, and a willingness to have both written down.
