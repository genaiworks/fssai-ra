# Related work: what this builds on, and what it adds

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Read the normative requirements in [`SPECIFICATION.md`](SPECIFICATION.md), then the claim boundary in [`ASSURANCE.md`](ASSURANCE.md).

## Why this page exists

Almost no individual mechanism in this repository is new. Reference monitors,
separation of duties, capabilities, lattice labels, and declassification all
predate modern AI by decades. Recent research applies several of them to language
model agents with strong results. A framework that claims to be a foundation must
say which ideas it inherits, where it overlaps with current work, and what it
contributes that the prior work does not. It must also avoid claiming novelty it
has not earned.

## Foundations it inherits

| Prior work | Idea | How this repository uses it |
|---|---|---|
| Anderson (1972), the reference monitor | every access passes a tamper-proof, always-invoked, verifiable mediator | the executor and the disclosure gate are the mediators; the model is never one |
| Saltzer and Schroeder (1975) | least privilege, complete mediation, fail-safe defaults, separation of privilege | complete mediation at execution and at release; unknown capabilities and endpoints fail closed |
| Denning (1976), the lattice model | information flows only upward in a lattice of security classes | the data label joins by union of classes and subjects and intersection of purposes and zones |
| Clark and Wilson (1987) | integrity through well-formed transactions and separation of duties | profile transitions are the well-formed transactions; requester and approver must differ |
| Hardy (1988), the confused deputy | authority should travel with the request, not sit ambiently with the program | holder-bound grants and delegation chains bound to their bearer |
| Myers and Liskov (1997), decentralised labels | owners control how their data may flow, with explicit declassification | declassification only through a declared rule and an independent owner-side approval |
| Nissenbaum (2004), contextual integrity | privacy is appropriate flow for a context, not secrecy | purposes, recipients, and zones are the context; a flow outside them is refused |

## Current work it overlaps with

| Work | What it provides | Overlap | What this repository adds | What that work does that this does not |
|---|---|---|---|---|
| **CaMeL**, Debenedetti et al. (2025) | separates control flow from untrusted data and attaches capabilities to values so injected content cannot redirect an agent | capability-style tracking of what data may do | institutional purpose, live consent, residency, break-glass, exact-output declassification by a named role, and an evidence chain tied to domain packs | a program interpreter that tracks dependencies of individual values, evaluated on the AgentDojo benchmark |
| **FIDES**, Costa et al. (2025) | a planner that tracks confidentiality and integrity labels and deterministically enforces flow policies | label propagation and deterministic enforcement outside the model | the same labels joined with purpose and zone, a contract and coverage method, and governance roles for release and declassification | integrity labels that constrain what untrusted data may cause, and selective hiding primitives inside planning |
| **Design patterns for securing LLM agents**, Beurer-Kellner et al. (2025) | six patterns that trade agent utility for provable injection resistance | a pattern catalogue for agent security | patterns for authority, disclosure, oversight capacity, and assurance, each bound to executable evidence | a systematic taxonomy of agent control-flow restrictions against prompt injection |
| **AI control**, Greenblatt et al. (2024) | safety protocols that remain effective when the model is deliberately trying to subvert them | the premise that safety should not depend on the model being aligned | the premise applied to institutional authority and data boundaries, with bounded enumeration instead of red-team games | protocols that use trusted weaker models to monitor and edit an untrusted stronger one |
| **Alignment faking**, Greenblatt et al. (2024) | evidence that a model can behave differently when it believes it is being trained | motivates treating model behaviour under test as unreliable evidence | containment invariants enumerated against enforcement code, so they do not depend on model behaviour | direct empirical study of model behaviour; nothing here measures a model |
| OWASP LLM and agentic top 10, MITRE ATLAS, NIST AI 600-1, ISO/IEC 42001 | threat catalogues and management-system requirements | vocabulary for the threat catalogue | executable binding of each catalogued threat to a control and a test, with residuals stated | organisational scope, certification pathways, and broad community consensus |

## The contribution, stated narrowly

The claimed contribution is not a new mechanism. It is a composition, a method,
and evidence.

1. **Two rules made executable together.** One constitutional layer governs both
   what an AI system may do and what it may see and release. The labels,
   capabilities, and approvals share one evidence chain and one set of domain
   packs.
2. **Institutional semantics inside the enforcement point.** Purpose, live consent,
   processing zone, emergency access with review debt, recipient clearance, and
   exact-output declassification by a declared role are enforced by the gate. They
   are not left to policy documents.
3. **A method that measures itself.** A seven-field contract with coverage checked
   against running tests, bounded enumeration against independent reference
   predicates, stateful random sequences, ablation of every check, a comparison with
   a careful conventional design, and a threat catalogue that must state residuals.
4. **Transfer as a first-class test.** The same kernel and generated suites run
   across education, corporate, healthcare, financial, and government packs. Each pack reports its own
   denominators, and transfer has repeatedly exposed real defects.

## What prior work does better, today

- CaMeL and FIDES track dependencies of individual values automatically through
  program execution. This gate labels whole sessions by default, and value by value
  only when a trusted orchestrator names the values it used; the gate recomputes
  those labels and over-labels when an unnamed value appears verbatim.
- The AI control literature measures protocols against actively adversarial
  models. Nothing here evaluates a real model.
- Standards bodies provide consensus, certification pathways, and organisational
  scope that a research repository cannot.

A deployment that needs value-level precision should combine a planner of the
CaMeL or FIDES kind with the institutional gate described here, not choose between
them.

## References

- Anderson, J. P. (1972). *Computer Security Technology Planning Study*. ESD-TR-73-51, US Air Force Electronic Systems Division.
- Saltzer, J. H., and Schroeder, M. D. (1975). The protection of information in computer systems. *Proceedings of the IEEE*, 63(9), 1278–1308. https://doi.org/10.1109/PROC.1975.9939
- Denning, D. E. (1976). A lattice model of secure information flow. *Communications of the ACM*, 19(5), 236–243. https://doi.org/10.1145/360051.360056
- Clark, D. D., and Wilson, D. R. (1987). A comparison of commercial and military computer security policies. *IEEE Symposium on Security and Privacy*, 184–194.
- Hardy, N. (1988). The confused deputy (or why capabilities might have been invented). *ACM SIGOPS Operating Systems Review*, 22(4), 36–38. https://doi.org/10.1145/54289.871709
- Myers, A. C., and Liskov, B. (1997). A decentralized model for information flow control. *Proceedings of the 16th ACM Symposium on Operating Systems Principles*, 129–142. https://doi.org/10.1145/268998.266669
- Nissenbaum, H. (2004). Privacy as contextual integrity. *Washington Law Review*, 79(1), 119–157.
- Greenblatt, R., Shlegeris, B., Sachan, K., and Roger, F. (2024). AI control: Improving safety despite intentional subversion. *Proceedings of the 41st International Conference on Machine Learning*. https://arxiv.org/abs/2312.06942
- Greenblatt, R., et al. (2024). Alignment faking in large language models. https://arxiv.org/abs/2412.14093
- Debenedetti, E., et al. (2025). Defeating prompt injections by design. https://arxiv.org/abs/2503.18813
- Costa, M., et al. (2025). Securing AI agents with information-flow control. https://arxiv.org/abs/2505.23643
- Beurer-Kellner, L., et al. (2025). Design patterns for securing LLM agents against prompt injections. https://arxiv.org/abs/2506.08837
