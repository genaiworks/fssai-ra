# FSSAI-RA

[![Tests](https://github.com/genaiworks/fssai-ra/actions/workflows/tests.yml/badge.svg)](https://github.com/genaiworks/fssai-ra/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![License Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-0B7261.svg)](LICENSE)
[![Release v1.0.0](https://img.shields.io/badge/release-v1.0.0-4C566A.svg)](https://github.com/genaiworks/fssai-ra/tree/v1.0.0)

> **A model may propose an action. It cannot manufacture the authority to execute it.**

**Fail-Secure Sovereign AI Reference Architecture** is an extensible,
public-interest platform for specifying and testing the authority boundaries of
agentic AI. It runs in memory on a laptop, or as a reference deployment with
FastAPI, PostgreSQL, Redis, Kafka, PySpark, Iceberg, object storage, a local
model through Ollama, and a React operator console.

The companion paper is *Trust by Construction: A Testable Architecture for
Sovereign AI Agents in Education*, prepared for the **UNU Macau AI Conference
2026** — *AI × Education: AI for Learning, Learning for AI* — and its
UNU–Springer proceedings.

## Start here

**If you came from the paper or the panel**

- [Extended abstract](fssai-ra/paper/extended-abstract.md) — the submission
- [Conference deck](fssai-ra/docs/presentation/slides.html) and [speaker script](fssai-ra/docs/presentation/speaker-script.md)
- [Results, with their limits](fssai-ra/evaluation/results/RESULTS.md)
- [Assurance claims and evidence](fssai-ra/docs/ASSURANCE.md) — every claim, its test, and what it does not mean

**If you are reviewing it**

- [Check every claim in ten minutes](fssai-ra/docs/REVIEWERS.md) — offline, no Docker
- [Responsible AI: risk → mitigation → test → result](fssai-ra/docs/RESPONSIBLE_AI.md)
- [Who benefits, and how we would know](fssai-ra/docs/IMPACT.md)

**If you want to use it**

- [Authority Boundary Worksheet](fssai-ra/docs/worksheet/) — one capability, seven fields, fifteen minutes, in a browser
- [Oversight capacity calculator](fssai-ra/docs/oversight/) — how much review can you actually supply? Offline, sends nothing anywhere
- [The authority boundary lab](fssai-ra/docs/LAB.md) — ninety minutes, offline, for people who will govern one of these systems
- [The two-minute demonstration](fssai-ra/docs/DEMO.md) — `python scripts/demo.py`
- [Adoption playbook](fssai-ra/docs/ADOPTION.md) — a 30/60/90-day path
- [Procurement questions](fssai-ra/docs/PROCUREMENT.md) — the seven fields as a supplier questionnaire
- [Project overview and architecture](fssai-ra/README.md)
- [Extension guide](fssai-ra/docs/EXTENDING.md) · [Distributed platform](fssai-ra/docs/PLATFORM.md) · [Threat model](fssai-ra/docs/SECURITY.md)

## Quickstart

```bash
git clone https://github.com/genaiworks/fssai-ra.git
cd fssai-ra/fssai-ra
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"

pytest                                            # 394 deterministic tests, fully offline
fssaira doctor                                    # what is this deployment, really?
fssaira verify   profiles/student_support.yaml    # 240 states, 5 invariants, 0 violations
fssaira evaluate profiles/student_support.yaml    # 30 adversarial + 6 benign + 8 ablations
fssaira conformance --backend sql                 # does it hold on another backend?
fssaira oversight profiles/student_support.yaml --sweep   # how much review can you supply?
fssaira challenge                                 # the open adversary corpus, scored
make reviewer                                     # all of the above, one command
fssaira init my-domain                            # scaffold your own
```

No network, no model weights, no GPU. Release `v1.0.0` contains 187 deterministic
tests; current source has 394. Both include a bounded model checker over the
profile's declared authority space, a portable conformance suite, and versioned
machine-readable results. These establish specified properties in a synthetic
environment; they are **not** a security certification or evidence of production
readiness.

## Central rule

> A model may propose an action. It cannot manufacture the authority to execute it.

For every consequential capability, identify the protected asset, permitted
operation, independent enforcement point, accountable owner, failure test,
evidence artifact, and recovery response. Then test the real side effect.

A capability whose seven fields cannot be filled is a capability nobody is ready
to automate. That is the diagnostic, not an inconvenience.

## What v1.0.0 adds

| | Question it answers | Result |
|---|---|---|
| Bounded model checking | What about the combination nobody imagined? | 240 states, 0 violations |
| Ablation-measured coverage | Is each control load-bearing, or decorative? | 8 of 8 restored their harm |
| Portable conformance | Does it hold after you replace a component? | 25 checks, 2 backend profiles |
| Utility baseline | Does legitimate work still complete? | 6 of 6, false-denial rate 0.0 |
| Controlled comparison | Compared with how agents are built today? | 0% → 29% → 100% contained |

Three things the current branch adds, each answering a question the release could
not:

| | Question it answers | Result |
|---|---|---|
| Oversight capacity | How much review can an institution actually supply? | 11 reviewers sustain 2,640 actions/day; 4 → 0 merit failures under load |
| A second domain | Does the method work where it was not designed? | 4,800 states, 0 violations, no library change — and it found a real defect |
| Open adversary corpus | Is the adversary ever someone other than the author? | 10 entries, 3 arms, and an externally-contributed count of 0 that we print |

Plus single-transaction execution on PostgreSQL, privilege invariance, real
authentication, a React console, and a worksheet, playbook, and procurement
questionnaire for people adopting it. See [`CHANGELOG.md`](fssai-ra/CHANGELOG.md).

> **A system can be perfectly accountable and completely unreviewed.** Every
> control here routes a consequential action to a named human. Push the queue
> past that human's attention and all of it still passes its tests. That is why
> review capacity is now declared, bounded, and published rather than assumed —
> and why the reviewer degradation curve is labelled a *declared parameter*
> everywhere it appears. No human was observed. See
> [assurance §7](fssai-ra/docs/ASSURANCE.md).

Every figure above is generated by `scripts/generate_results.py` and checked
against the paper and the deck by `tests/test_paper_alignment.py`. If prose and
code disagree, the build fails.

Licensed under Apache-2.0. Contributions that preserve explicit assurance
boundaries are welcome.
