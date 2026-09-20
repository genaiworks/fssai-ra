# Trust by Construction: Secure-by-Design Patterns for Agentic AI in Learning Institutions
Scale Intelligence Without Scaling Implicit Authority

Rachana Srivastava
Enterprise Architect | AI Systems Researcher
UNU Macau AI Conference 2026 | Extended abstract
AI × Education: AI for Learning, Learning for AI

## Introduction

In a learning institution, AI agents now read student records, change school systems and delegate work to other agents. A transcript assistant should retrieve the requested record, propose a correction and deliver the approved result to the authorised registrar. It should not open another student's file because a document tells it to, approve its own correction, or keep releasing data after revocation. Indirect prompt injection can redirect tool-integrated agents [1].

The harder problem is that permitted steps can combine into an outcome no one allowed. A reader, a summariser and a publisher may each hold a sound tool list and still form a path from a student transcript to a public page. No one agent misbehaves. The chain does.

Trust by Construction treats every agent, including its coordinator, as an untrusted proposer. Separate enforcement services mediate protected reads, delegation, effects and disclosure under one rule: proof before power. Ten design patterns connect institutional policy to executable refusals.

The work builds on control-flow separation [2], data-flow control [3] and agent design patterns [4]. Those bound what one agent may do. The open question is what a set of permitted agents may do as a group. The aim is an integration and test method, not a new security primitive. Proof here means a check of stated rules against trusted state. It does not mean proof that a model is truthful or that a grade is fair.

## Development Section 1 Methodology Core Argument and Case Context

The model makes proposals. Separate, trusted software decides which operations may run. Scoped leases let an agent call the gateway without letting it rewrite the gateway's policy. The ten patterns are a declared authority ceiling (P1), a task contract (P2), a credentialless runtime (P3), attenuated delegation (P4), mediated context (P5), reauthorised memory (P6), typed effects (P7), sealed release (P8), a restricting monitor (P9) and a declared task graph (P10).

@FIG:patterns

Figure 1. Ten patterns across one task lifecycle. Columns show each pattern's primary stage.

The threat model allows malicious or colluding agents, poisoned content and a monitor that is wrong. It assumes trusted enforcement code, protected state, known operators and adapters that cannot be bypassed. A task purpose picks an approved operation and resource policy; it does not establish what the agent means.

Every boundary does the same five things: authenticate the caller, load current state, intersect rights, validate the exact operation, then commit. The case makes this concrete. A registrar asks for a grade correction. The assistant may read the named record, because the lease names that record and no other. It drafts a change, but the write is refused until the instructor confirms, because the contract names a second approver. The receipt binds that approval to that exact draft, so a later, different write cannot reuse it. Revoke the grant mid-task and the queued write fails, even though it was approved when it was drafted.

The design hypothesis is falsifiable: under an unchanged contract, adding workers must not admit a prohibited effect, information path or total spend. That must be checked on the whole composition, not on each worker alone.

A swarm is a set of agents coordinated on one institutional task. The coordinator may split work and propose workers, but spawning is itself mediated. Each child gets its own identity, an expiry and authority no wider than its ancestors, task and workload ceiling. Replanning changes a proposed task graph, and a trusted gate must admit each new node and edge before use. Agreement among agents is evidence for review, never a credential.

@FIG:swarm-architecture

Figure 2. Proposed swarm extension. Parallel workers share one task budget and revocation epoch; every handoff and effect crosses enforcement. The diagram specifies architecture, not measured distributed performance.

Parallelism must not multiply resources. All descendants draw on task-wide limits for calls, records read, bytes released and consequential effects, plus a workload ceiling across tasks. Depth, population and time limits bound recursive spawning. Atomic reservations precede dispatch, and completion or cancellation settles them without double spending. External effects need adapter reconciliation when the outcome is unclear: a database rollback cannot unsend an email.

Information composes the same way. Trusted mediation binds source labels to artifacts and messages, so agents cannot strip them by rewording or dropping citations. Outputs inherit restrictions from all exposed context, including retained memory. Reuse with a clean context needs a new isolated context; an agent's claim to have forgotten is not enough. Combining inputs intersects permitted recipients and purposes, and any relaxation needs a separately authorised release. This can over-restrict useful summaries, a deliberate trade.

@FIG:composition

Figure 3. Composition changes the security question. A tool allowlist does not stop a permitted publisher disclosing another agent's protected input. Labels and recipient checks must survive the handoff; agreement among agents supplies no release authority.

At fan-in, a trusted gate checks provenance, current authority, artifact identity and destination before accepting results. Revocation raises the task epoch, so queued work, stale leases and later release chunks fail revalidation. Disclosed information cannot be recalled. A fresh check alone leaves a check-then-act race: strict revocation needs authorisation and commit serialised against revocation, or an adapter that rejects stale epochs. Partitioned workers must stop when freshness cannot be shown, trading availability for bounded authority. Physical isolation, egress control and trustworthy connectors stay deployment duties.

## Development Section 2 Results Analysis and Impact

The FSSAI-RA reference kernel runs offline without model weights or a GPU, so every figure can be rerun on a laptop. Its recorded six-profile evaluation explores 55,440 bounded configurations with no invariant violation, 180 hostile scenarios, all contained, and 58 benign workflows, all completed [5]. These profiles reuse an authored scenario suite: the counts and that state space are linked synthetic checks, not 180 independent attacks, outside validation or production reliability estimates.

Three findings do more work than the totals. First, composition is not covered by local correctness. Against ten delegation attacks, an unguarded chain contained none, validating each hop against its immediate delegator contained two, and verifying the whole chain contained ten. The middle arm is a real control and what a careful engineer builds; a majority of the risk classes pass straight through it.

Second, sequence testing found what step testing missed. A stateful harness caught a summary drafted while access was valid but released after consent was withdrawn, which single-step enumeration had passed. Release now rechecks live state, and removing that control makes the violation reappear.

Third, a second domain found what one domain could not. The academic-records profile exposed a declared approval role the runtime silently ignored, because the enforcement map was built only from consequential rules.

Eight claims are implemented and bound to a named offline regression test: delegation cannot enlarge authority, parallel siblings cannot multiply a budget, separate processes cannot race a commit, composition cannot erase a restriction, memory cannot carry a restriction away, revocation invalidates in-flight authority, a release cannot resume after revocation, and checking each step is not checking the sequence. That the same bound holds across distributed workers is specified and not yet evaluated. Undoing a delivered external effect is not claimed.

@FIG:claim-matrix

Figure 4. What is built and what is proposed. Each claim names the mechanism that enforces it, its status and the offline test that exercises it.

The next evaluation should compare an unmediated swarm, separate local controls, shared task enforcement and a deny-all baseline under identical workloads, injecting malicious coordination, repeated spawning, label stripping, duplicate delivery, revocation during execution and network partitions. It should report prohibited effects beside benign completion, false refusals, tail latency and resource cost, and increase worker count and graph depth to test non-amplification. A single prohibited composite outcome falsifies the claim within the tested boundary.

Security remains conditional on complete mediation and sound policy. A compromised enforcer, covert output channel or permissive policy can invalidate containment, and a malicious monitor can deny useful service even when it cannot escalate privilege. Authorised actions may still be inaccurate, discriminatory or educationally harmful, so review, appeal, accessibility and pedagogical evaluation remain necessary. A decision receipt binds the policy version, task epoch, source lineage, artifact digest, recipient and outcome, so review need not treat model reasoning as proof. Receipts need access controls and retention limits, so an audit trail does not become another store of student data.

For institutions, this turns trust into something a buyer can demand and an auditor can rerun: named enforcement points, a filled task contract, declared review limits and fresh evidence. Procurement can require the refusal suite before signing, and a regulator can check purpose and revocation as running controls rather than as policy text. Because the contract sits outside the model, a school can change model or vendor and rerun the same tests, so the safety case need not be rebuilt each time. Sovereignty becomes control of keys, data flow and exit, not the location of a server.

## Conclusion

For AI for Learning, a registrar can inspect record access, correction authority and release destinations. Institutions should deploy bounded, reversible workflows first, qualify connectors, and evaluate with staff and students before expanding autonomy. A named owner must handle escalation and appeals, and students must be told how to contest a result. Human review capacity is finite: workloads exceeding it should queue or reduce autonomy rather than treat a nominal approval step as effective oversight.

For Learning for AI, learners can inspect a forged approval, poisoned memory and a colluding agent chain, then observe which boundary refuses each action. This complements UNESCO's human-centred AI competency agenda [6] with practical understanding of authority and redress, and offline verification lowers the kit a teaching lab needs.

The design supports SDG 4 through accountable school workflows and SDG 16 through explicit, contestable institutional authority. Because the contract is enforced outside the model, institutions can require the same authority contract and refusal suite across model and vendor changes, so governance attaches to a workflow whose authority can be withdrawn rather than to a vendor's assurances.

Scaling intelligence is not the risk; scaling implicit authority is. Increasing autonomy should expand useful computation within a declared mandate. It should never silently expand the mandate itself.

## References

[1] Zhan, Q., et al. (2024). InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents. Findings of ACL. https://arxiv.org/abs/2403.02691

[2] Debenedetti, E., et al. (2025). Defeating Prompt Injections by Design. arXiv:2503.18813. https://arxiv.org/abs/2503.18813

[3] Costa, M., et al. (2025). Securing AI Agents with Information-Flow Control. arXiv:2505.23643. https://arxiv.org/abs/2505.23643

[4] Beurer-Kellner, L., et al. (2025). Design Patterns for Securing LLM Agents against Prompt Injections. arXiv:2506.08837. https://arxiv.org/abs/2506.08837

[5] Srivastava, R. (2026). FSSAI-RA reference implementation. Repository snapshot 9bb35a1: fssai-ra/evaluation/results/v1.0.0-domain-pack-matrix.json, fssai-ra/tests/test_tbc_sdk.py and fssai-ra/tests/test_delegation.py. https://github.com/genaiworks/fssai-ra/tree/9bb35a1

[6] UNESCO (2024). AI Competency Framework for Students. https://unesdoc.unesco.org/ark:/48223/pf0000391105
