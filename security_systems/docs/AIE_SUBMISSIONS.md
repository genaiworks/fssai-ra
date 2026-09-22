# AI Engineer CODE Summit 2026 (San Francisco, Nov 10–12): three submissions

Every number is from `evidence/<domain>.json` (regenerate with `make evidence`).
**Before submitting:** publish the repository (Apache-2.0) and put its URL in each pitch. Reviewers click links.

---

## 1. Talk (priority)

**Session Title**

Per-Hop Auth Caught 2 of 10 Agent Attacks. Whole-Chain Verification Caught 10.

**Description**

Your coding agent spawns sub-agents, and every hop passes its authorization check. The chain still leaks your production database password into `#general`.

I ran ten hostile delegation chains against three architectures:

| Architecture | Hostile chains caught (of 10) |
|---|---|
| Trust the leaf's claimed scope | **0** |
| Check each hop against its parent (careful RBAC) | **2** |
| Recompute authority from the root on every call | **10** |

A legitimate chain completes under all three. Per-hop checks catch forged and widened hops. They miss the eight attacks that live *in the chain*:

- bearer-chain reuse
- confused deputy
- undisclosed beneficiary
- a loop that launders authority
- an orphaned delegation
- depth evasion
- a worker re-delegating deploy rights
- a chain rooted in nothing

Live against a synthetic production estate, a hijacked worker tries five ways to ship an unreviewed build: no approval, forged "ADMIN" text, a borrowed approval, a swapped target, and calling the tool server directly. Production doesn't move. Then I delete one control at a time and the attacks come back.

You leave with three rules and the open-source guard that enforces them, one decorator per tool:

1. **Re-derive authority from the root on every call.** A chain authorizes only the agent it names.
2. **Bind human approval to the exact action.** Principal, tool, resource and argument digest, executed exactly once.
3. **Let labels survive summarization.** A worker's output carries everything it read, and no agent can declassify its own output.

**Session format:** Talk (preferred), Workshop

**Special Flags:** None

**Speaker/Session Pitch** (committee only)

Sub-agents, background agents, and MCP tool chains have become the default architecture, while the authorization pattern most frameworks document is still per call. This talk puts a number on the gap, 2 of 10 versus 10 of 10, from an open, runnable harness rather than a thought experiment, and ends with a guard attendees can adopt the same week.

I'm Rachna Srivastava, an enterprise architect who has spent the past year building a reference implementation of "trust by construction" for agentic systems (independent work, in a personal capacity). The accompanying research paper was submitted to an academic venue in September 2026. The repository has 203 tests. The same attack suites run unchanged against devtools, healthcare, finance, and government domains. The whole demo runs offline in about ten seconds with no API key, so it can't fail on conference Wi-Fi, and every attendee can rerun it in their seat. Repo: `<URL>`.

**Possible Tracks:** Security, Coding Agents, Multi-Agent Systems

---

## 2. Workshop

**Session Title**

Guard Your Agent's Tools, Then Try to Break Them: A Hands-On Lab

**Description**

Bring a laptop, with Python 3.10+ and no API key. You'll leave with your own agent's tools behind a guard, and proof that the guard does something.

**Part 1: guard it (30 min).** Wrap a coordinator and three workers' tools with `trustkernel.guard`, one decorator per tool:

- Delegation is re-derived from the root on every call.
- Deploys need an Ed25519 human approval bound to the exact arguments, and run exactly once.
- A worker's data label follows its output, so a credential can't reach `#general` through a summarizer.

**Part 2: break it (40 min).** Attack your own setup and the reference kernel:

- **Replay the ten delegation attacks** that per-hop auth misses: a sibling's stolen chain, a confused deputy, an orphaned hop, a re-delegated deploy.
- **Run the 25 falsifiers**, judged by what reached the model, the channel, or production, never by whether an error was raised.
- **Ablate.** Remove one control, rerun, and watch the harm return. Then find the two redundant pairs.
- **Write a "speed up releases" policy PR** that tries to weaken the kernel. The shipped one is rejected on 39 counts.

**Part 3: bring your domain (10 min).** Four domains ship: devtools, healthcare, finance, and government. A new one is a YAML pack plus a cast. `trustkernel check` tells you if it's miswired, and the full attack suite runs against it with no new tests.

**Session format:** Workshop

**Special Flags:** None

**Speaker/Session Pitch** (committee only)

AI Engineer audiences want to leave with something running. Setup is `pip install pyyaml cryptography`: seconds, with no key, no GPU, and no network after install. A CI job holds that promise to a 60-second budget from a cold clone. Every exercise produces a stable denial code or an observed leak, so the room can check each other's results. I built the guard, kernel, and attack suites, so I can take any question down to the line of code. Repo: `<URL>`.

**Possible Tracks:** Security, Coding Agents, Evals

---

## 3. Talk

**Session Title**

Your Agent Guardrail Is Decorative Until You Delete It

**Description**

Most agent guardrails are tested by checking that they raise an error. That proves the code path exists, not that it's what stopped the attack.

This talk is a measurement protocol for agent controls, shown running across four regulated domains:

- **Judge by effect, not by error.** The oracle never asks the guardrail whether it refused. It checks whether a protected value reached the model, an output reached a recipient, or production changed.
- **Ablate every control.** Rerun each attack with exactly one control removed, then restored. In 25 of 29 ablations the harm comes back. The other four are two redundant pairs, and removing each pair together lets the attack through. The table is credible *because* some rows say no.
- **Prove your attacker can win.** A red team that finds nothing is indistinguishable from one that can't run. Ours finds 0 violations in 300 attacks, and 103–105 once the execution mediator is removed. A bandit attacker goes from 0 forbidden outcomes to 60 of 60.
- **Test the policy, not just the code.** Policy is a YAML pack the kernel refuses to load if it weakens a guarantee. Its failure tests are *derived from the pack itself*: every consequential transition is executed with the wrong role and then the right one.
- **Validate the harness.** A static checker catches fixtures that would make an ablation measure the wrong control.

The same suites run unchanged against devtools (a production deploy), healthcare (a warfarin dose), finance (a credit limit), and government (a benefit termination), with identical verdicts.

**Session format:** Talk

**Special Flags:** None

**Speaker/Session Pitch** (committee only)

Evals for *capability* are mature. Evals for *containment* are mostly anecdotes and screenshots. This talk gives engineers a reusable protocol (effect-based oracles, per-control ablation, attacker positive controls, and policy-derived contract tests) and shows it holding across four domains. It complements my delegation talk (#1) rather than repeating it: #1 is *what* breaks in multi-agent chains; this is *how to prove* any fix works. If only one is accepted, I'd prioritize #1. Repo: `<URL>`.

**Possible Tracks:** Evals, Security, Agent Reliability
