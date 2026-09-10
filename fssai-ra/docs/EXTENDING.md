# Extending the reference architecture

This guide helps a university, public agency, researcher, or student adapt the
teaching profile without inheriting claims that its environment has not tested.

## Begin with one consequential action

Write one sentence in this form:

> The agent may propose **operation** for **scope**, but only **authority** may
> commit it after reviewing **evidence**, and **owner** restores service if the
> control is unavailable.

Choose a narrow, synthetic workflow before connecting records or real tools. Define
a manual service path so fail-secure automation does not become denial of service.

## Add a complete control-contract entry

Add YAML under `contract/` with these fields:

```yaml
id: DOMAIN-UNIQUE-ID
protected_asset: What can be harmed or disclosed
permitted_operation: The narrow action and scope the agent may request
enforcement_point: The independent component that makes the decision effective
owner: The role accountable for policy and recovery
test: The attempt and concrete side effect to observe
evidence_artifact: What a reviewer can later reconstruct
failure_response: How automation stops and service continues
```

The enforcement point must inspect the actual operation, target, arguments, current
state, and identity. A model-generated explanation is recorded context, not an
authorization source.

## Write the failure test first

For every consequential capability, test at least:

- altered target or arguments after approval;
- expired, revoked, wrong-audience, or reused approval;
- stale authoritative record after review;
- direct backend access using the agent identity;
- evidence-service and policy-service unavailability;
- retry before and after a simulated commit;
- one legitimate task, to measure false denial and operational burden.

Assert the real side effect, not only a policy function's return value. Count writes,
inspect controlled sinks, reconstruct the evidence bundle, and disclose the test
boundary and denominator.

## Preserve profile labels

- **Teaching profile:** synthetic data, in-memory services, shared-host limitations.
- **Institutional pilot:** separately administered identities, networks, keys,
  evidence custody, restoration, human continuity, and domain review.
- **Hardware-isolated profile:** a physical topology and interface inventory, tested
  directional gateway, maintenance procedure, and all institutional controls.

Passing one profile never implies assurance for another. A hardware diode constrains
one link; it does not validate imported text or close output, maintenance, telemetry,
or operator paths.

## Submit an extension

Open an issue describing the workflow, protected people and records, threat model,
manual fallback, and intended profile. A pull request should include the contract
entry, implementation, attack test, benign test, ablation where meaningful, evidence
example, and limitations. Use synthetic or properly licensed data only. Never include
credentials, private model artifacts, or identifiable student records.
