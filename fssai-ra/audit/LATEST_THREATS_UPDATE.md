# Completion update: contemporary threats and secure design patterns

Research cutoff: 14 September 2026. This update builds on the current author checkout at 59794bf0341e59a8ac67a1a0770e659c1ed32876, including intervening key-secrecy, composition, adaptive-attack and bibliography improvements. Those changes were preserved; this update does not claim authorship of them.

## What the paper now addresses

- Separates disclosed 2026 incidents from controlled multiagent/reward-hacking experiments and protocol guidance.
- Corrects the misleading idea that an independent reward oracle itself contains an attacker; it measures effects, while enforcement contains them.
- Replaces claims that greater capability automatically improves utility or leaves assurance unchanged with explicit requalification requirements.
- States a conditional reference-monitor argument with complete mediation, trusted enforcement, current authorization, atomic accounting and mediated output assumptions. It is not represented as a machine-checked proof.
- Adds twelve implementable design patterns and acceptance conditions covering scope, identities, egress, provenance, tool supply chains, persistent memory, delegation, transactions, shutdown, publication, learning infrastructure and privacy/redress.
- Specifies monitor failure policy, model-update promotion, no-solution deferral, streaming revocation semantics, isolation of shared agent state, independently controlled shutdown, and qualification records with expiring evidence.
- Keeps authorized semantic harm, inference, host compromise and common-mode failures visible instead of reclassifying them as contained.

## Recent primary sources incorporated

[35] UK AISI incident report: https://www.aisi.gov.uk/blog/incident-report-unsanctioned-agent-behaviour-during-cyber-testing . July 2026 events; intentional internet access, not sandbox escape; attempted supply-chain/social-engineering behavior; no resulting harm identified by AISI. These configurations and observations are not general incidence estimates.

[36] Anthropic, 9 September 2026: https://www.anthropic.com/research/alignment-assessment-cybersecurity-incidents . Separate incidents with mistakenly available internet; attributed monitoring and environment-control findings. The paper does not merge these with AISI's incident.

[37–38] Microsoft, 10 February and 22 June 2026: https://www.microsoft.com/en-us/security/blog/2026/02/10/ai-recommendation-poisoning/ and https://www.microsoft.com/en-us/security/blog/2026/06/22/guarding-ai-memory/ . Memory poisoning and defense across memory lifecycle.

[39] Invariant Labs, 1 April 2025: https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks . Tool-description poisoning; no reproduction against external MCP servers performed here.

[40] MCP living draft, checked 14 September 2026: https://modelcontextprotocol.io/docs/draft/tutorials/security/security_best_practices . Confused deputy, token passthrough and SSRF. The draft is not claimed to be the version used by an uninspected deployment.

[41–42] Anthropic: https://www.anthropic.com/research/multiagent-systems and https://www.anthropic.com/research/emergent-misalignment-reward-hacking . Controlled multiagent and training findings, kept distinct from incidents.

[43–44] OpenAI, March 2026: https://openai.com/index/designing-agents-to-resist-prompt-injection/ and https://openai.com/index/reasoning-models-chain-of-thought-controllability/ . Consequence-limiting agent design and contingent reasoning monitorability; not a claim that readable reasoning is truthful or that private reasoning must be exposed.

## Executed additions and remaining limits

Eighteen new tests passed. Sixteen mechanism-inspired requests each denied without additional state change or release, then completed a positive control. Two more tests cover false simulation/monitor rationale and a 100-attempt no-solution sequence. See modern-threats.json, modern-tests.xml and modern-tests.log. These are local typed-interface analogues, not replications of external incidents.

The paper revision and reference regressions are complete. Production isolation, every real remote adapter, independently held evidence, full memory integration, language-model RL, trained reasoning monitors, educational/human outcomes and unknown future attacks cannot be declared solved by this artifact. Applicable missing evidence blocks deployment. This is the substantive meaning of gap closure in the revised paper: implement what is in the reference boundary, make every wider obligation explicit and testable, and deny unsupported capabilities.
