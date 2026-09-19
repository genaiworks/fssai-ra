# Architecture implementation review

**Documentation navigation:** [Documentation map](README.md) · [SDK guide](TBC_SDK.md)

The supplied 657-page architecture is a design catalogue, not a description of a fully qualified deployment. `audit/architecture-controls.json` preserves all 109 distinct control identifiers, source pages, implementation pointers and open scope. Related test files are navigation aids; they do not verify every requirement in a control. The register deliberately separates local implementation, partial reference coverage, deployment requirements and missing features.

## Newly enforced behavior

The SDK dispatch accepts schema version 1, including legacy requests without a version, and rejects other versions, duplicate keys, nonfinite JSON and server-authority fields. Existing strict size and nesting bounds remain active.

An operator can call `TrustRuntime.invalidate_source(token, source, reason=...)`. The service persists the exact source binding digest and emits a structured evidence event. Context reads, derivative use and affected agent dispatch reject that binding after quarantine. Summaries, memory and handoffs retain source lineage, so they cannot wash a quarantined source. The rule survives reopening the database and also rejects retrieval by a fresh task. A normal authority restore does not remove source quarantine; source repair must produce a new binding. This is conservative: a contaminated session remains unusable. Already released bytes cannot be recalled.

## Integration components and their limits

`integration.messages` defines strict context and effect proposal contracts. The main SDK uses its versioned parser. The standalone context/effect dataclasses are adapter contracts, not a claim that every SDK operation now accepts those wire shapes.

`integration.supply.ModelBundle` hashes eight components: weights, tokenizer, configuration, system prompt, adapters, retrieval configuration, tools and runtime. Every component requires a SHA256 digest. `FrozenCatalog` rejects manifest drift across server, description, schemas, executable, declared effects and risk. High-risk direct model exposure is denied. These components do not attest a running model or automatically intercept external tools. A trusted adapter must bind measured artifacts to them before dispatch.

`integration.network.DestinationPolicy` authorizes explicit HTTPS hosts and path prefixes, rejects credential-bearing URLs, queries, fragments, traversal and nonglobal resolved addresses, and requires public data for public egress. It returns resolved addresses, TLS identity and a byte ceiling. It opens no socket. A qualified transport must use those addresses, validate TLS, enforce the ceiling and reauthorize every redirect. DNS rebinding prevention cannot be claimed from URL validation alone.

`kernel.state` specifies an explicit uncertain-outcome state that cannot be retried as if no effect occurred. This is a state contract, not an implemented remote reconciliation service.

## Reproduce the evidence

From `fssai-ra/`, after installing development dependencies:

```sh
python -m pytest
python scripts/check_tbc_alignment.py
python scripts/check_architecture.py
python scripts/verify_architecture.py
python scripts/check_paper_revision.py
python scripts/generate_results.py --check
```

The last command compares the existing experiment figures to a fresh run. `verify_architecture.py` executes the six seven-field capability contracts in `contract/capabilities/architecture.yaml`, emits JUnit and logs, and binds the claim register to the current Python source and tests. A missing, failed, skipped or xfailed test is not machine-verified. Local evidence is not independent attestation. Named accountable owners are role assignments that an institution must staff; the repository cannot establish their organizational independence.

## Remaining qualification work

The local Python boundary cannot confine hostile native code. Deployment work includes workload federation, process and network isolation, key custody, external kill paths, physical retention/deletion, independent evidence witnesses and credential rotation. Integration gaps include revocable streaming, browser profiles, generic external effect reconciliation, full SBOM and dependency impact handling, canary promotion, policy differential simulation and the complete production training/promotion lifecycle. Existing sector profiles and mediators remain available; the new joined SDK still uses its synthetic education adapter.

These are open requirements, not passing controls. Broader architecture coverage requires implementations and target-specific evidence, not changing status labels or adding paper claims.

**Recommended next:** [SDK enforcement and operational boundaries](TBC_SDK.md).
