# AI Con USA 2027 (Seattle, June 6–11, 2027): submission

Deadline: **October 18, 2026**. Figures come from `evidence/devtools.json`.

---

**Session Title**

Authority Doesn't Compose: Breaking and Fixing Multi-Agent Delegation with Chain Verification, Taint Labels, and Ablation

*Alternates:*
- The Confused Deputy Is Back, and It Spawns Sub-Agents
- Per-Hop Auth Caught 2 of 10 Agent Attacks. Whole-Chain Verification Caught 10.

**Topic areas:** AI Security & Safety (primary); Agentic AI; AI Governance, Regulation, & Compliance

**Session type:** Concurrent session (45–60 min), technical deep dive with live attacks. Also open to leading a facilitated open space on ablation testing for agent controls.

**Audience:** Engineers and architects building or securing multi-agent systems. Advanced-intermediate; comfortable reading Python and thinking about authorization.

**Abstract**

Every hop in your agent chain can pass its authorization check while the chain as a whole does something nobody authorized. Agent frameworks inherit an authorization model built for single callers. They validate each tool call against the caller's scope, and the caller's scope against its immediate parent. Across ten hostile delegation chains, that careful per-hop design caught **2 of 10**. Recomputing authority from the root grant on every call caught **10 of 10**, and let the benign chain through in both designs.

This session dissects why, with live attacks against an open kernel that runs offline on a laptop:

- **Delegation as a verifiable chain, not a context object.** Each hop is a signed, attenuating capability (tools × operations × resources × action class × expiry). The executor re-derives effective authority from the root and enforces nine invariants: monotone attenuation, hop provenance, root anchoring, temporal containment, acyclicity, a depth bound, non-delegable consequence, holder binding (defeating bearer-chain reuse), and beneficiary attenuation (the confused deputy). Per-hop validation enforces only the first two. Ablating each invariant in turn shows all nine are load-bearing.
- **Information flow survives summarization.** Model output inherits the join of the labels of everything the session read. A worker that labels its own summary "public" can't launder a credential into a broad chat channel. Remove the taint rule and the password lands there live.
- **Exact-action approval.** An Ed25519 human approval is bound to one proposal digest, audience, role, and expiry, and is single-use under a 32-way race. The read authority behind the action is re-checked at write time (a TOCTOU fix), so revoking a data grant voids an already-approved change.
- **Proving controls are load-bearing.** An effect-based oracle judges what reached the model, the channel, or production, never the error code. Per-control ablation shows 25 of 29 controls are load-bearing and 4 are redundant pairs. Seeded and bandit attackers find nothing, and each has a positive control that removes one mediator and wins: 105 of 300, and 60 of 60.
- **Policy as a validated artifact.** Domain policy is a YAML pack that the kernel refuses to load if it weakens a guarantee. A malicious "fast lane" pack fails 39 checks. The same attack suite runs unchanged against devtools, healthcare, finance, and government packs.

**Key takeaways**

1. The nine delegation invariants, and why validating each hop against its parent enforces only two of them.
2. How to carry data labels through LLM summarization, so agents can't declassify their own output.
3. A reusable verification protocol for agent controls: effect-based oracles, per-control ablation, and attacker positive controls.

**Speaker bio**

Rachna Srivastava is an enterprise architect and AI systems researcher. Working independently and in a personal capacity, she built an open reference implementation of "trust by construction" for agentic AI: a kernel in which agents hold no authority of their own, and every guarantee is tested by attacking it and removing the control that provides it. Her accompanying research paper was submitted to an academic venue in September 2026.

**Why this session**

Multi-agent orchestration, sub-agents, and tool-server chains are becoming the default architecture, while authorization practice is still per-call. This session names the specific failure classes, shows each one exploited and fixed live, and gives a measurement method attendees can apply to their own stack. Every number is reproducible from one repository in seconds, fully offline, so the demo carries no network risk.
