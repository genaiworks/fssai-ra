# Pilot protocol: measuring what software cannot

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Policy route](README.md#policy-leader-route) · [Engineering route](README.md#ai-engineer-route) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Agree the go and no-go criteria below with the accountable owners, then configure the deployment with [`GOVERNED_DISCLOSURE.md`](GOVERNED_DISCLOSURE.md).

## Why this exists

Every software gap in this repository can be closed with code and tests. One
cannot: whether a governed AI system actually serves the people it affects. That
needs a pilot with real users, a denominator, a comparison, and permission to stop.

This protocol turns the remaining gap into a study an institution can run. It
does not close the gap. A pilot that follows it produces the evidence that does.

## Scope

- **One capability, one sensitive read path, one domain pack.** For example,
  discharge-summary drafting from medications and allergies, credit-limit
  affordability summaries, or eligibility caseworker briefings.
- **Synthetic data first, then real data only after approval.** A pilot on real
  records needs ethics or data-protection approval, a named accountable owner, and
  a signed decision to proceed.
- **A comparison arm.** The current service without the AI assistant, measured
  over the same period and population.

## Pre-conditions: do not start without these

| Pre-condition | Evidence |
|---|---|
| Durable state configured | `FSSAI_DISCLOSURE_STORE` points at PostgreSQL or SQLite, and a restart drill shows revocations and consent withdrawals survive |
| Institutional grants | grants issued by the authorization server and verified with `FSSAI_DISCLOSURE_TOKEN_ISSUER`, `_AUDIENCE`, and `_JWKS_URL` |
| Live consent | `FSSAI_DISCLOSURE_CONSENT_URL` points at the consent system of record, and a withdrawal drill takes effect at the next read and release |
| Real record source, least privilege | a FHIR or SQL source whose credential can read only the declared fields |
| Model endpoint in an approved zone | `FSSAI_MODEL_ENDPOINT` names an endpoint declared in the pack |
| Falsifiers pass on the deployed pack | `fssaira thesis` and `fssaira disclosure` on the pack actually deployed, with results archived |
| Concurrency qualified | the process race run against the production database engine, not only SQLite |
| Named fallback staffed | the pack's manual fallback owner has capacity for every refusal |

## Indicators computed from evidence

Run weekly and at the end:

```bash
fssaira pilot-report exported-evidence.json --output indicators.json
```

| Indicator | Why it matters | Signal to investigate |
|---|---|---|
| Read and release refusal rate, by code | shows whether the policy fits the work | a code dominating refusals, or refusals rising week on week |
| Consent and revocation refusals | shows live state is taking effect | zero, when withdrawals are known to have happened |
| Break-glass opened, reviewed, awaiting, and review latency | emergency access must be rare and reviewed | awaiting reviews older than the pack's policy, or rising volume |
| Claimed downgrade attempts | a model or integration claiming a lower label than its inputs | any sustained non-zero rate |
| Value labels falling back to session | the orchestrator omitted a source it used | any non-zero rate is an integration defect to fix |
| Evidence chain intact | every other indicator depends on it | any break stops the pilot |

## Outcomes that need people, not logs

These are the measures the indicators cannot supply. Each needs a named method,
a denominator, and a comparison arm.

| Outcome | Method |
|---|---|
| **Wrong refusals** | sample refused requests weekly; a domain expert blind to the arm judges whether access was appropriate |
| **Wrong releases** | sample released outputs; judge whether recipient, purpose, and content were appropriate |
| **Service effect** | time to complete the task, backlog, and escalations, against the comparison arm |
| **Accuracy and harm of outputs** | expert review of a stratified sample, including errors of omission |
| **Fairness** | refusal, delay, and error rates by the subgroups the institution is obliged to monitor |
| **Reviewer attention** | break-glass and declassification reviewers re-review a seeded sample with known answers |
| **Affected-person experience** | complaints, appeals, and a short survey where lawful and appropriate |
| **Staff workload and cost** | time on fallback, review, and support, against the comparison arm |

## Go and no-go criteria

Agree thresholds before the pilot starts and publish them with the results.

- **Stop immediately** if the evidence chain breaks, a release is found after a
  revocation or withdrawal, or any confirmed disclosure reaches an uncleared
  recipient.
- **Stop and redesign** if wrong refusals exceed the agreed threshold or degrade
  service against the comparison arm, or if break-glass reviews exceed the
  pack's review window.
- **Proceed to a wider pilot** only if every falsifier still passes on the
  deployed pack, no stop condition occurred, and the independent assessment in
  [`GAPS.md`](GAPS.md) is complete.

## Reporting

Publish the pack version, deployment configuration, falsifier and disclosure
results, indicators, sampled outcome judgements with denominators, stop events,
and every limitation. A pilot report without refusals, errors, and limits is
not evidence.
