# The seven fields as procurement questions

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

**One blocking finding is enough to defer.** Not to reject — to defer, with the
finding named, until it is closed. Most suppliers can close these; many have
simply never been asked in these terms.

---

## Three questions to ask about the supplier's own evidence

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
