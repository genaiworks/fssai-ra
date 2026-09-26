# Adopting Trust by Construction: the recommended path for organisations

> **Documentation navigation:** [Documentation map](README.md) · [Framework](FRAMEWORK.md) · [MCP gate](MCP_GATE.md) · [Glossary](GLOSSARY.md)

> **Recommended next:** Describe your first agent in a use-case file and run `fssaira framework plan` on it.

This page is for a team about to build or buy an AI agent. It tells you how
much of the framework that agent needs, what to build first, and when not to
automate at all. You do not need to read the pattern catalogue before you
start.

## The recommendation in five sentences

1. Keep authority out of the model: the model proposes, and separate software
   decides what runs.
2. Size the controls to the use case. A meeting summariser and a payments swarm
   need different amounts of this framework, and building the wrong amount
   fails either way.
3. Put every tool behind a gate on day one. It is the cheapest control that
   removes the most authority from the model.
4. Make a named person approve each irreversible action, bound to its exact
   arguments, until you have evidence that you can safely stop.
5. Keep evidence that the enforcing system cannot rewrite, and ask vendors for
   a verifier's report rather than their own summary.

## Step 0: triage one use case (an hour)

Describe the agent in about ten yes-or-no answers. Three worked examples are in
[`examples/use-cases/`](../examples/use-cases/).

```yaml
name: Student-record correction assistant
reads_protected_data: true
regulated_data: true
external_effects: true
irreversible_effects: false
multi_agent: false
third_party_tools: false
untrusted_input: true
autonomy: human_approves_consequential   # or human_in_every_loop / autonomous
```

```bash
fssaira framework plan my-agent.yaml --write-assessment assessment.yaml
```

The planner returns:

- a **target level**, with the reason for every rise;
- the controls that apply, and the conditional ones that do not, each with the
  reason it does not apply;
- a **first sprint**;
- **stop conditions**: combinations under which the agent should not run
  autonomously however many controls you build.

A planner answer is a judgement written down so that you can argue with it.
The rules are in [`adoption_plan.py`](../src/fssaira/adoption_plan.py).

| Example | Target | Controls | Stop condition |
|---|---|---|---|
| Internal meeting summariser | 1 Access-controlled | 7 | none |
| Student-record correction assistant | 3 Disclosure-governed | 31 | none |
| Autonomous accounts-payable swarm | 5 Evidenced | 59 | untrusted email can steer irreversible payments with no human in the loop |

**If the planner prints STOP, believe it.** The payments swarm is not refused
forever. The planner is saying to keep a person approving each payment until
that approval exists and is measured.

## Step 1: the first sprint (a week or two)

This is the same for every agent, and each item is independently useful:

- **No credentials in the agent** (IDN-1). Keys live in services the agent can
  only call.
- **Declared interfaces only** (IDN-3), with **expiring leases** that cannot
  widen (IDN-2).
- **A named owner and a manual route** for when the agent refuses (GOV-1). If
  no one owns the refusal, the refusal strands the person being served.
- **A tamper-evident log** that records intent before each effect and no
  protected values (EVD-1).
- **An explicit deployment posture** (GOV-6), so a teaching default cannot run
  in production.
- **Every tool behind the [MCP gate](MCP_GATE.md)**. The Claude Agent SDK,
  the OpenAI Agents SDK, LangGraph and most IDEs can use MCP servers, so this
  step changes configuration, not code:
  - `scan` flags poisoned tool text, and `lock` records a named person's
    approval of the exact text.
  - Scope each sensitive argument to exact values.
  - Mark each irreversible tool `approval: required`.
  - Give the session an expiry and a call budget.

  A complete example is in
  [`examples/mcp/gate.authority.yaml`](../examples/mcp/gate.authority.yaml).

## Step 2: build to your target, in dependency order

```bash
fssaira framework assess assessment.yaml --roadmap
```

The roadmap lists the controls you still need, in waves by level, with
dependencies first. Each control names an owner, what to build, and the test,
command or signed attestation that proves it. Answer `evidenced` only when that
proof has run in your deployment. `implemented` is a claim, and the assessment
reports the gap between what you claim and what you can evidence.

## Step 3: prove it, and keep proving it

- `fssaira assure report` produces a digest-stamped report. Run it in CI on
  every change to the model, vendor, policy or enforcer.
- Qualify your own store and connectors against the revocation invariants
  before an agent can reach anything irreversible (EFF-2, EFF-3).
- Size review to the floor you declare with `fssaira assure staffing`. If
  review is understaffed, add people; never lower the floor.
- Run witnesses and time servers under administration that is really
  separate, before anyone relies on the record in an appeal (level 5).

## What to ask a vendor

- **Assurance level:** the level they claim, and the assessment file behind it.
- **Refusal suite:** the suite for that level, which you run yourself.
- **Assurance report:** the digest, which should match the one you produce
  from the same inputs.
- **Tool supply:** the MCP lock file for every tool the agent can reach, and
  who approved each entry.
- **Isolation report:** a report measured from inside the agent's cell, not
  just a diagram.
- **Review capacity:** the capacity declared and the staffing behind it.

A vendor who can only offer a document has not met any of these.

## When not to use an agent

Do not automate an action when all three of these hold:

- it cannot be undone;
- nothing can confirm that the value the agent proposes is right;
- no person reviews it.

Mediation can prove that an action was allowed. It cannot prove that the action
was right. For that combination the correct design is a person making the
decision, with the agent drafting.

## What this path does not give you

This path gives you the controls and the tests. It does not give you evidence
from your own deployment. The reference implementation has been exercised on
synthetic packs and fixtures. It has not had an external security review, and
it has not been run in a field pilot. Before relying on it for regulated or
irreversible work:

- have the gate and your enforcement code reviewed independently;
- run a bounded pilot under the [pilot protocol](PILOT_PROTOCOL.md);
- measure false denials, latency and deferrals alongside containment.
