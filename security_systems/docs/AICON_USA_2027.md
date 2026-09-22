# AI Con USA 2027 (Seattle, June 6–11, 2027): submission

Deadline: **October 18, 2026**. Figures come from `evidence/<domain>.json`.

---

**Session Title**

Authority Doesn't Compose: Securing Multi-Agent AI with Chain Verification, Taint Labels, and Ablation

*Alternates:* "The Confused Deputy Is Back, and It Spawns Sub-Agents" · "Per-Hop Auth Caught 2 of 10 Agent Attacks. Whole-Chain Verification Caught 10."

**Topic areas:** AI Security & Safety (primary); Agentic AI; AI Governance, Regulation, & Compliance

**Session type:** Concurrent session, a technical deep dive with live attacks. Also open to leading a facilitated open space on ablation testing for agent controls.

**Audience:** Engineers and architects building or securing multi-agent systems. Intermediate to advanced; comfortable reading Python and reasoning about authorization.

**Abstract**

Every hop in your agent chain can pass its authorization check while the chain as a whole does something nobody authorized. Agent frameworks inherit an authorization model built for single callers: each tool call is checked against the caller's scope, and the caller's scope against its immediate parent. Across ten hostile delegation chains, that careful per-hop design caught **2 of 10**. Recomputing authority from the root grant on every call caught **10 of 10**, and a legitimate chain completed under every design.

This session dissects why, with live attacks against an open kernel that runs offline on a laptop:

- **Delegation as a verifiable chain, not a context object.** Each hop is a signed, attenuating capability (tools × operations × resources × action class × expiry). The executor re-derives authority from the root and enforces nine invariants: attenuation, hop provenance, root anchoring, temporal containment, acyclicity, a depth bound, non-delegable consequence, holder binding, and beneficiary attenuation. Per-hop validation enforces only the first two.
- **Labels that survive summarization.** Model output inherits the join of everything the session read. A worker that calls its own summary "public" can't launder a credential into a company-wide channel. Remove the taint rule and the password lands there live.
- **Exact-action approval.** An Ed25519 human approval is bound to one principal, tool, resource, and argument digest, and executes exactly once under a 32-way race. The read authority behind the action is re-checked at write time, so revoking a data grant voids an already-approved change.
- **Proving each control is load-bearing.** An effect-based oracle judges what reached the model, the channel, or the system of record, never the error code. In 25 of 29 ablations the harm returns; the other four are named redundant pairs. Each attacker has a positive control that removes one mediator and wins.
- **One kernel across regulated domains.** Policy is a YAML pack the kernel refuses to load if it weakens a guarantee. The same suites run unchanged against software delivery, healthcare, financial services, and public benefits, with identical verdicts.

Attendees leave with an open-source guard that adds these checks to their own tool dispatcher, one decorator per tool.

**Key takeaways**

1. The nine delegation invariants, and why validating each hop against its parent enforces only two of them.
2. How to carry data labels through LLM summarization, so agents can't declassify their own output.
3. A reusable verification protocol for agent controls: effect-based oracles, per-control ablation, and attacker positive controls.

**Speaker bio**

Rachna Srivastava is an enterprise architect and AI systems researcher. Working independently and in a personal capacity, she built an open reference implementation of "trust by construction" for agentic AI: a kernel in which agents hold no authority of their own, and every guarantee is tested by attacking it and removing the control that provides it. Her accompanying research paper was submitted to an academic venue in September 2026.

**Why this session**

Multi-agent orchestration, sub-agents, and tool-server chains are becoming the default architecture, while authorization practice is still per call. This session names the specific failure classes, shows each exploited and fixed live across four regulated domains, and gives attendees both a measurement method and a guard they can adopt. Every number is reproducible from one repository, fully offline, so the demo carries no network risk.
