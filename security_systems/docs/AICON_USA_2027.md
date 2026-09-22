# AI Con USA 2027 (Seattle, June 6–11, 2027): submission

Deadline: **October 18, 2026**. Figures come from `evidence/devtools.json`.

---

**Session Title**

Your AI Agent Passed Every Check and Still Leaked the Password: Governing Agents by Construction

**Topic areas:** AI Security & Safety (primary); Agentic AI; AI Governance, Regulation, & Compliance

**Session type:** Concurrent session (45–60 min). Also open to leading a facilitated open space on "What does a load-bearing AI control look like in your organization?"

**Audience:** Practitioners, architects, and technical leaders deploying AI agents in regulated or high-consequence settings. Intermediate; no security background required.

**Abstract**

AI agents now read sensitive records, hand work to other agents, and propose changes to production systems. Most organizations govern them with per-step permission checks and policy documents. In a controlled experiment, that careful per-step approach caught 2 of 10 multi-agent attacks. Recomputing authority across the whole chain of agents caught all 10, and still let legitimate work through.

This session shares what I learned from building an AI agent governance kernel and then attacking it relentlessly. The core idea is simple: agents may *propose* and *request*, but only independent mediators may *act* or *release data*. The lessons are practical:

- **Why "every step was authorized" isn't a defense.** Live, I show a chain where no single agent misbehaves and a production password still reaches a company-wide chat channel. Then I show the one control that stops it.
- **How to prove a control is doing its job.** Remove it and rerun the attack. Of 29 controls, 25 proved load-bearing; the other four were redundant pairs, which is also worth knowing before an audit.
- **Why policy needs a floor.** A "speed things up" configuration change that quietly weakened oversight was rejected on 39 counts before it could load.
- **Turning governance into evidence.** Signed human approvals bound to one exact action, tamper-evident records, and a test suite that turns compliance claims into reproducible results.

The same kernel is configured, not rewritten, for software delivery, healthcare, financial services, and government services. Attendees leave with a checklist they can apply to any agent deployment.

**Key takeaways**

1. Authorizing each agent step is not the same as authorizing the chain. Know the eight delegation failure patterns per-step checks miss.
2. A control you've never removed and re-tested is an assumption. Use ablation to separate load-bearing controls from decoration.
3. Governance can be engineered as enforceable, testable configuration that produces evidence auditors and regulators can rerun.

**Speaker bio**

Rachna Srivastava is an enterprise architect and AI systems researcher. Working independently and in a personal capacity, she built an open reference implementation of "trust by construction" for agentic AI: a kernel in which AI agents hold no authority of their own, and every governance claim is tested by attacking it. Her accompanying research paper was submitted to an academic venue in September 2026. She focuses on making AI governance measurable for high-consequence and regulated environments.

**Why this session / notes to the committee**

Most AI governance talks stay at the level of principles, and most AI security talks stay at the level of individual prompts. This session sits between the two. It shows a concrete, runnable way to govern *agents*, the fastest-growing and least-governed part of enterprise AI, with numbers that the audience can reproduce on a laptop. The live demonstration runs fully offline in seconds, so it carries no conference-network risk.
