# FSSAI-RA

[![Tests](https://github.com/genaiworks/fssai-ra/actions/workflows/tests.yml/badge.svg)](https://github.com/genaiworks/fssai-ra/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![License Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-0B7261.svg)](LICENSE)
[![Tag v0.4.0](https://img.shields.io/badge/tag-v0.4.0-4C566A.svg)](https://github.com/genaiworks/fssai-ra/tree/v0.4.0)

**Fail-Secure Sovereign AI Reference Architecture** is a runnable teaching-profile
implementation for testing the authority boundaries of agentic AI. Its synthetic
student-support workflow connects governance requirements to independent enforcement,
failure tests, reconstructable evidence, and named recovery ownership.

The companion paper is *Trust by Construction: A Testable Architecture for Sovereign
AI Agents in Education*, prepared for the UNU Macau AI Conference 2026.

## Start here

- [Project overview and architecture](fssai-ra/README.md)
- [Assurance claims and evidence](fssai-ra/docs/ASSURANCE.md)
- [Five-minute reproducible demonstration](fssai-ra/docs/DEMO.md)
- [Extension guide](fssai-ra/docs/EXTENDING.md)
- [Threat model and residual risks](fssai-ra/docs/SECURITY.md)
- [Extended abstract](fssai-ra/docs/extended-abstract.md)

## Quickstart

```bash
git clone https://github.com/genaiworks/fssai-ra.git
cd fssai-ra/fssai-ra
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
python examples/demo_student_support.py
fssaira evaluate profiles/student_support.yaml --output evaluation-report.json
```

Release `v0.4.0` contains 32 deterministic tests and a versioned eight-scenario
machine-readable evaluation result. These tests establish specified
properties in a synthetic in-memory environment; they are not a security
certification or evidence of production readiness.

## Central rule

> A model may propose an action. It cannot manufacture the authority to execute it.

For every consequential capability, identify the protected asset, permitted
operation, independent enforcement point, accountable owner, failure test, evidence
artifact, and recovery response. Then test the real side effect.

Licensed under Apache-2.0. Contributions that preserve explicit assurance boundaries
are welcome.
