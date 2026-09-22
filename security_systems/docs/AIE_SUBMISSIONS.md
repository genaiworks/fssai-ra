# AI Engineer CODE Summit 2026: three submissions

Every number below comes from `evidence/devtools.json` (regenerate with `make evidence`).

---

## Submission 1: headline talk

**Session Title**

Per-Hop Auth Caught 2 of 10 Agent Attacks. Whole-Chain Verification Caught 10.

**Description**

Your coding agent spawns sub-agents, and every hop passes its authorization check. The chain still leaks your production database password into `#general`.

I ran ten hostile delegation chains against three architectures:

| Architecture | Hostile chains caught (of 10) | Benign chain |
|---|---|---|
| Trust the leaf's claimed scope | **0** | completes |
| Check each hop against its parent (careful RBAC) | **2** | completes |
| Recompute authority from the root on every call | **10** | completes |

Per-hop checks catch forged and widened hops. They miss the eight attacks that live *in the chain*:

- bearer-chain reuse
- confused deputy
- undisclosed beneficiary
- authority laundering through a loop
- orphaned delegation
- depth evasion
- a machine passing on consequential authority
- a chain rooted in nothing

Live on stage, against a synthetic production estate:

- A hijacked worker tries five ways to push an unreviewed build to prod: no approval, forged "ADMIN" text, a borrowed approval, a swapped target, and calling the tool server directly. Production doesn't move.
- 32 concurrent callers race one valid approval: exactly one deploy, and 31 get the same receipt back.
- A human approves a change, then the data grant behind it is revoked, so the write is refused.
- I delete one control at a time and the attacks come back. 25 of 29 controls are load-bearing. The other four are named defence-in-depth pairs.

You leave with three rules you can implement in your own agent stack on Monday.

**Session format:** Talk (preferred), Workshop (happy to expand)

**Special Flags:** None

**Speaker/Session Pitch** (committee only)

Every coding-agent stack shipped in the last year added sub-agents, background agents, or MCP tool chains. Almost all of them authorize the *hop* and never the *chain*. This talk puts a number on that gap, 2 of 10 versus 10 of 10, from an open, runnable harness rather than a thought experiment, and shows the exploits live.

I'm Rachna Srivastava, an enterprise architect who has spent the past year building a reference implementation of "trust by construction" for agentic systems (independent work, in a personal capacity). The accompanying research paper was submitted to an academic venue in September 2026. Everything on stage is reproducible from one repository with `python demo.py`, in about two seconds, with no API key or GPU. The demo therefore can't fail on conference Wi-Fi, and every attendee can rerun it in their seat.

**Possible Tracks:** Security, Coding Agents, Multi-Agent Systems

---

## Submission 2: hands-on workshop

**Session Title**

Break My Agent Kernel: 25 Attacks, One Laptop, No API Key

**Description**

Bring a laptop and leave with a working method for proving your agent guardrails actually do something.

We clone a governed agent kernel and attack it. The kernel runs coding agents over a synthetic production estate: services, secrets, pull requests and deploys. Everything runs locally in seconds. Agents can read, summarize, spawn workers and propose. Only independent mediators can execute, release data, or delegate.

What you'll do:

1. **Run the 25 falsifiers:** unauthorized deploy, forged approval, replay, a 32-way race, prompt injection from a signed CI log, output laundering ("my summary is public"), model substitution, router compromise, and evidence tampering. Each is judged by what reached the model, the channel, or production, never by whether an error was raised.
2. **Ablate:** remove one control, rerun, and watch the harm return. Learn why a control that changes nothing when deleted was never doing anything.
3. **Attack the config, not the code:** write a "speed up releases" policy PR that tries to weaken the kernel. The shipped malicious one is rejected 39 ways.
4. **Point an adaptive attacker at it:** a bandit attacker scored by an independent oracle, with a positive control that removes a mediator and shows the attacker *can* win.
5. **Write your own falsifier:** it's one Python function. If it breaks the kernel, you've found a real bug. Open the issue.

Python 3.10+. An optional local Ollama model can play the attacker.

**Session format:** Workshop

**Special Flags:** None

**Speaker/Session Pitch** (committee only)

AI Engineer audiences want to leave with something that runs. The repository is built for that: `pip install pyyaml cryptography && python demo.py` takes seconds, needs no key or GPU and no network after install, and has a CI job that holds the cold-clone promise to a 60-second budget. The workshop is structured so every attendee gets from "it holds" to "here is exactly which control stopped it" to "I broke it, or I proved I couldn't." I built the kernel, the falsification engine and the attack suites, so I can take any question down to the line of code.

**Possible Tracks:** Security, Evals, Coding Agents

---

## Submission 3: methods talk

**Session Title**

Your Agent Guardrail Is Decorative Until You Delete It

**Description**

Most agent guardrails are tested by checking that they raise an error. That proves the code path exists, not that it's what stopped the attack.

This talk is a method for measuring agent controls the way you'd measure anything else in production:

- **Judge by effect, not by error.** The oracle never asks the guardrail whether it refused. It checks whether a protected value reached the model, whether output reached a recipient, and whether production changed.
- **Ablate every control.** Rerun each attack with exactly one control removed, then restored. In our kernel 25 of 29 controls are load-bearing. The other four are redundant pairs, and removing both halves of a pair lets the attack through. The table is only credible because some rows say "no".
- **Prove your attacker can win.** A red team that finds nothing is indistinguishable from one that can't run. A seeded attacker finds 0 violations in 300 attempts, and 105 once the execution mediator is removed. A bandit attacker finds 0 forbidden outcomes, and 60 of 60 in its positive control.
- **Make the domain configuration, not a fork.** Policy lives in a YAML pack, covering data classes, purposes, recipients, transitions, approver roles and delegation bounds. The kernel refuses to load any pack that would weaken it. A malicious "fast lane" pack fails 39 checks. The same attack suite runs unchanged against every domain pack: devtools, healthcare, finance and government.

**Session format:** Talk

**Special Flags:** None

**Speaker/Session Pitch** (committee only)

Evals for *capability* are mature. Evals for *containment* are mostly anecdotes and screenshots. This talk gives engineers a concrete, reusable protocol (effect-based oracle, per-control ablation, attacker positive controls, policy-as-validated-config) and shows it running on real numbers. It complements rather than overlaps my delegation talk. That one is about *what* breaks in multi-agent chains; this one is about *how to prove* your fix works. If only one of my submissions is accepted, I'd prioritize the delegation talk (#1).

**Possible Tracks:** Evals, Security, Agent Reliability
