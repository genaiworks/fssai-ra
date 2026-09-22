# AIE CODE Summit SF 2026 — submission-ready proposals

Select **Brand new session** for each submission. Submit in the order below. Each session stands alone and offers a different outcome. Select the closest available track labels; the form's exact dropdown options may differ.

# Proposal 1 — recommended first submission

## Session Title

Your Coding Agent Has Approval. Is It for This Deploy?

## Description

Learn how to stop a coding agent from turning approval for one build into permission to deploy another. In this live Python demo, we follow a release request from the agent’s tool call to the resulting system state—and attack every boundary along the way.

A worker borrows another agent’s authority. An approved build changes before execution. A retry presents a forged approval for a cached receipt. We show the failed assumptions, then implement the checks: bind caller identity outside the model’s request, verify delegated authority, and tie approval to the effective tool arguments—including defaults.

The implementation uses a small dispatcher with application-defined tools, resources, and approval roles. You can adapt the same interface to your own coding-agent stack. We demonstrate legitimate replay without a second callback and explain what still requires durable idempotency at the target service.

You’ll leave with a runnable dispatcher, adversarial regression tests, and an integration worksheet covering identity, credentials, approval, and recovery. The demonstration runs locally with scripted requests and synthetic state, without a model API. Every result is tied to an observable effect and an explicit implementation boundary.

## Session format

Stage Talk — 15–20 minutes.

## Special Flags

None.

## Speaker/Session Pitch

I’m Rachna Srivastava, an enterprise architect presenting independent work in a personal capacity. I built the Python reference implementation and attack harness used in this session.

As coding agents gain access to deployment tools, the useful question is exactly what turns their request into an authorized change. This talk answers it through one software-delivery workflow, inspectable code, and failures found in the implementation itself. A cached-result shortcut skipped approval validation even though the underlying executor checked signatures correctly; the demo makes that integration mistake visible.

The audience receives a reusable dispatcher and tests, with clear responsibilities for caller authentication, credential isolation, and durable execution. The local demonstration avoids dependence on conference connectivity or a hosted model. The talk stays focused on the execution boundary; broader evaluation and disclosure exercises are available in the supporting artifact.

## Possible Tracks

Coding Agents; Security; Agent Infrastructure.

---

# Proposal 2 — evaluation and failure analysis

## Session Title

203 Tests Passed. Our Agent Guard Still Had Bypasses.

## Description

Learn how to find the security failures your agent tests never exercise. We start with a 203-test suite that passed, then show how its integration wrapper still let a modified context erase a data label and a forged approval retrieve a cached receipt.

The kernel checked its rules. The wrapper took a different path. We trace that gap, reproduce a cached-receipt failure pattern, and write a regression that observes released data. A second example changes a synthetic deployment record and then raises “denied.” A test that trusts the refusal misses the write; an independent effect oracle catches it.

From these failures, we build an evaluation protocol: define observable harm, preserve legitimate work, remove a control, restore it, and verify that the attacker can succeed against the weakened system. One paired ablation demonstrates why removing a redundant check may leave the same attack blocked.

You’ll leave with a copyable Python effect oracle, an experiment worksheet, and runnable positive and negative controls. The wider harness contains 25 falsifiers and 29 ablation configurations; the session focuses on what those tests missed. All demonstrations use synthetic fixtures, and their limits are part of the result.

## Session format

Stage Talk — 15–20 minutes.

## Special Flags

None.

## Speaker/Session Pitch

I’m Rachna Srivastava, an enterprise architect presenting independent work in a personal capacity. I built the reference implementation, falsification harness, and ablation experiments behind this session.

Teams connecting agents to internal tools need evidence about the resulting state. A refusal message or a passing test count cannot supply that evidence by itself. This session turns defects found in my own integration into a practical method attendees can apply to theirs.

The contribution is the failure investigation and its reusable artifacts: a small effect oracle, explicit attacker positive controls, legitimate-work checks, and a worksheet for reporting assumptions and outcomes. I show where the original evaluator stopped looking and how the new regressions cover that boundary. The talk is designed around two concrete failures and one ablation example, keeping the full experimental tables in the accompanying material.

## Possible Tracks

Evals; Security; Agent Reliability.

---

# Proposal 3 — hands-on workshop

## Session Title

Stop Your Coding Agent’s Summarizer from Leaking Secrets

## Description

Build a worker-to-summarizer pipeline that refuses to publish a credential—even when the summary calls itself “public.” In this hands-on Python workshop, you’ll track what each worker read, carry that label through handoffs, and enforce recipient policy before output reaches a channel.

Start with a deliberately incomplete implementation that leaks a synthetic secret. Repair three functions: label the read, propagate the label, and check the release. Keep two useful workflows working: a public metrics summary and an authorized security-team disclosure.

Then attack your repair. Try resetting the session, interrupting a read with an exception, and passing the result through a second worker. Inspect the actual output sink, remove a handoff check to expose the leak, and restore it. Seven supplied checks make the outcome visible.

You’ll leave with your completed example, regression checks, reference solutions, and a worksheet for mapping the same boundaries in your own tool pipeline. Starter code and recovery checkpoints keep the lab accessible. Bring Python 3.10+ and install the supplied dependencies beforehand; the exercises run locally without a model API, GPU, or production credentials.

## Session format

Workshop — 90 minutes.

## Special Flags

None.

## Speaker/Session Pitch

I’m Rachna Srivastava, an enterprise architect presenting independent work in a personal capacity. I built the guard, disclosure fixtures, and tests used in this workshop.

Multi-worker coding systems move information as well as authority. A summarizer can carry a credential into an output even when its own tool permissions are narrow. This workshop gives attendees a concrete way to connect read labels, handoffs, and recipient checks—and to find the missing connection by observing a leak.

The teaching kit includes editable starter code, two recovery checkpoints, a reference solution, seven output checks, and participant and instructor guides. The intentionally incomplete starter passes only the two legitimate-release cases; the solution passes all seven. The exercises include exception paths and session-reset attempts, plus explicit discussion of direct network access and other paths a decorator cannot secure. Attendees finish with working code and a transfer exercise for their own workflow.

## Possible Tracks

Multi-Agent Systems; Security; Coding Agents.
