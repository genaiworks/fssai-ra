# FSSAI-RA implementation

> **Canonical framework:** [Trust by Construction](docs/FRAMEWORK.md) · [P1–P34 catalogue](docs/framework/PATTERNS.md) · [Operational controls](docs/framework/CONTROLS.md). This guide is a supporting view of that single framework.

This directory contains the Python implementation of **Fail-Secure Sovereign AI Reference Architecture**, using the **Trust by Construction** approach. The platform supports research and integration across multiple sectors and publications.

[Project overview](../README.md) · [User guide](docs/USER_GUIDE.md) · [Features](docs/FEATURES.md) · [Documentation map](docs/README.md) · [Research and citation](docs/RESEARCH_GUIDE.md)

## Adopting agent swarms in your organisation?

Start at the framework's front door, [`docs/FRAMEWORK.md`](docs/FRAMEWORK.md): 50 controls in
nine domains, five maturity levels, a self-assessment with an ordered roadmap, a starter
workspace, and one reproducible assurance report.

```bash
fssaira framework init my-programme --org "My Org" --sector healthcare
fssaira framework assess my-programme/assessment.yaml --roadmap
fssaira assure report
```

## Start from this directory

You are in the application directory when `pyproject.toml`, `src/`, and `profiles/` are present. From here:

```bash
python3 scripts/joined_demo.py --output work/first-demo
```

Open `work/first-demo/viewer.html`. Expect five synthetic runs and `"verified": true`. Use a fresh output directory for every run.

For the CLI and tests:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,privacy,api]'
python scripts/demo.py --fast
fssaira profiles
fssaira verify profiles/student_support.yaml
fssaira evaluate profiles/student_support.yaml
```

Alternatively, use `make setup` from the parent repository root. Installation requires package access. The default examples execute locally without a model provider. See the [user guide](docs/USER_GUIDE.md) for Windows, API setup, and the console.

## Implementation areas

| Area | Read | Inspect or run |
|---|---|---|
| Policies and authority | [Architecture](docs/REFERENCE_ARCHITECTURE.md) | `profiles/`, `contract/`, `src/fssaira/control_plane.py` |
| Exact action and durable effects | [Resilience](docs/RESILIENCE.md) | `src/fssaira/exact_action.py`, `atomic_execution.py`, `joined_workflow.py` |
| Governed data | [Disclosure](docs/GOVERNED_DISCLOSURE.md), [Privacy](docs/PRIVACY_REFERENCE.md) | `src/fssaira/disclosure*.py`, `privacy_*.py` |
| Tasks, agents, memory, messages | [SDK](docs/TBC_SDK.md) | `src/fssaira/tbc/`, `scripts/tbc_demo.py` |
| Network and remote effects | [Developer guide](DEVELOPER_GUIDE.md) | `src/fssaira/integration/`, `remote_effects.py` |
| Evaluation | [Research guide](docs/RESEARCH_GUIDE.md) | `tests/`, `evaluation/results/`, `scripts/generate_results.py` |
| Services and operator tools | [Platform](docs/PLATFORM.md), [Console](console/README.md) | `deploy/`, `console/`, `src/fssaira/api.py` |
| Small-data or big-data deployment | [Scale tiers](docs/SCALE_TIERS.md) | `deploy/compose.small.yaml`, `deploy/compose.yaml`, `src/fssaira/scale.py`, `small_data.py` |

The [feature catalogue](docs/FEATURES.md) explains the purpose, usage, and limitations of each area. The [command reference](docs/COMMANDS.md) covers all top-level CLI commands and the major Make targets.

## Validation

Run `python scripts/reproduce.py` for a saved end-to-end evidence bundle, `python -m pytest` for the public runtime suite, and `python -m ruff check src tests scripts jobs adapters` for lint. Public checks do not need private manuscripts. `make manuscript-check` explicitly opts into historical paper checks and requires the local archive. See [validation tiers](docs/COMMANDS.md#validation-tiers).

Numeric snapshots and their denominators belong in [Results](evaluation/results/RESULTS.md); regenerate and inspect evidence before citing a result. These components have different trust boundaries and are not automatically one integrated, production-qualified system.

## Extend, operate, publish

- [Extend a domain or adapter](docs/EXTENDING.md).
- [Operate and recover a deployment](docs/OPERATIONS.md).
- [Review the security model](docs/SECURITY.md) and [open gaps](docs/GAPS.md).
- [Prepare another paper and cite this software](../publications/README.md).
- [Contribute changes](CONTRIBUTING.md).

Licensed under [Apache-2.0](../LICENSE). The software's [citation metadata](CITATION.cff) is independent of any one paper or conference.
