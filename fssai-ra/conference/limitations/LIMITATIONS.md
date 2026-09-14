# Limitations register

Every result in this package is a **fixture observation**: synthetic records, one process, a
declared education pack. None is a field result, a certification, or a probability of future safety.

| Area | What is established here | What is not established | What would establish it |
|---|---|---|---|
| Mediator isolation | Separate credentials and checks; neither mediator trusts the other | Process, host, or hardware isolation; both run in one Python process | Separate services and identities; a penetration test of the boundary |
| Model attestation | Signed manifests; digest, identity, expiry, purpose, class checks | That the runtime truthfully reports its loaded weights | TEE or hardware-rooted attestation quotes over the weights |
| Tokenization | Declared identity fields and detected contact details become session tokens | Anonymity; re-identification from quasi-identifiers in non-identity fields | A re-identification risk assessment on real data |
| Erasure | Governed copies unreadable after key destruction, verified by reading back | Released copies, runtime memory, heap residue, keys retained outside custody | HSM-backed custody; backup inventory audit; recipient obligations |
| Evidence | Hash chain plus signed checkpoints detect rewrite and truncation | Protection against a compromised notary key | Checkpoints published to an external transparency log |
| Human review | Capacity, timeout, escalation; overload never approves | Reviewer attention, accuracy, susceptibility to persuasion | An ethics-approved reviewer study (see `docs/PILOT_PROTOCOL.md`) |
| Delegation | Seven-axis attenuation and propagated revocation, fixtures and random sequences | Real orchestrator frameworks, cross-process revocation freshness | Adapter conformance runs on a real agent framework |
| Concurrency | One mutation from many threads in one process | Distributed linearizability | Fault-injected multi-node tests on the production database |
| Router | Malicious suggestions refused by gate and registry | Routing quality or cost optimality | Utility evaluation on representative tasks |
| Ollama path | Adapter and trace command; treated as untrusted | Any published figure from a real model; model output quality | Recorded runs across models with fixed prompts |
| Education effectiveness | Lab, dashboard, and literacy view exist and run | That learners understand more afterwards | Pre/post study with cohort, denominator, and consent |
| Kernel floor | Rejects named weakening patterns and missing contracts | That an at-floor pack is wise or lawful | Institutional review of each pack |
| Red teaming | Seeded grammar fuzzing and an optional local attacker model | Coverage of attacks nobody wrote down | External red-team submissions to `challenges/` |
| Performance | Local timings of mediator overhead | Production latency under load | Load tests on the deployed topology |
