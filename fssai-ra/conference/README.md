# Trust by Construction — conference evidence package

**UNU Macau AI Conference 2026 · AI × Education: AI for Learning, Learning for AI**
Panel: _Agentic AI in the Loop — From Autonomous Tools to Shared Capacity_

> **You do not have to trust the AI to govern what it can do.**
> Intelligence is untrusted; power and data are mediated.

This directory is the reproducible, adversarially tested demonstration of the paper's
central claim. It runs offline, on synthetic records, in one process, in under a minute.
Every figure in it is regenerated from execution, never typed.

## Reproduce everything

From the repository root (the directory above `fssai-ra/`):

```bash
make setup                   # create .venv and install
make test                    # the whole deterministic suite
make security                # education pack failure tests, custody, falsifiers, kernel floor
make falsify                 # every falsifier;          make falsify F=F19 for one
make ablation                # enabled / disabled / restored per control; F=F10 for one
make results                 # paper figures + conference/evidence/*
make conference-demo         # the live demonstration;   DEMO=7 for one demo
```

Inside `fssai-ra/` the same work is available as `fssaira conference …`:

| Command                                                      | What it does                                                    |
| ------------------------------------------------------------ | --------------------------------------------------------------- |
| `fssaira conference falsify [F01…F25]`                       | Attack the architecture; judge by what happened                 |
| `fssaira conference ablation [Fxx]`                          | Remove exactly one control, rerun, restore, rerun               |
| `fssaira conference trace --model honest\|malicious\|ollama` | One request through the ten governed steps                      |
| `fssaira conference stateful --remove consent`               | Random authority sequences, eight properties after every step   |
| `fssaira conference pack-check PATH`                         | Refuse a domain pack that weakens the kernel                    |
| `fssaira conference lab`                                     | The educational attack lab on `http://127.0.0.1:8765`           |
| `python scripts/conference_evidence.py --check`              | Do committed figures match a fresh run?                         |
| `python scripts/conference_benchmark.py`                     | Security overhead, separated from model latency                 |
| `python scripts/conference_redteam.py`                       | Seeded red-team fuzzing; `--ollama` adds a local attacker model |

Prerequisites: Python 3.10+, the `cryptography` package (installed by `make setup`). No network,
GPU, or model weights. Ollama is optional and never required for any published figure.

## What is here

| Path                                                                             | Contents                                                                                                                          |
| -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| [`education/governed-learning-pack.yaml`](education/governed-learning-pack.yaml) | The education domain pack: support, transcripts, aid, faculty feedback, challenge and redress, with seven-field control contracts |
| [`education/lab.html`](education/lab.html)                                       | Attack lab and system-literacy dashboard (served live by `conference_lab.py`)                                                     |
| [`attacks/malicious-domain-pack.yaml`](attacks/malicious-domain-pack.yaml)       | A pack that tries eight ways to weaken the kernel                                                                                 |
| [`evidence/`](evidence/)                                                         | Generated JSON for every experiment, plus [`SCORECARD.md`](evidence/SCORECARD.md)                                                 |
| [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md)                   | Planes, mediators, trust boundaries, and the ten-step path                                                                        |
| [`architecture/QUESTIONS.md`](architecture/QUESTIONS.md)                         | The uncomfortable questions about this architecture, answered                                                                     |
| [`limitations/LIMITATIONS.md`](limitations/LIMITATIONS.md)                       | What is not established, and what would establish it                                                                              |
| [`demos/DEMO_SCRIPT.md`](demos/DEMO_SCRIPT.md)                                   | A timed 12-minute live demonstration with fallbacks                                                                               |

## The modules behind it (`fssai-ra/src/fssaira/`)

| Module                                                                              | Role                                                                                  |
| ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `education_world.py`                                                                | A synthetic university wiring every real mediator; any control removable for ablation |
| `falsification.py`                                                                  | 25 falsifiers and the ablation runner                                                 |
| `authority_stateful.py`                                                             | Stateful testing against an independent reference model                               |
| `governed_request.py`                                                               | The ten-step trace and the system-literacy explanation                                |
| `key_custody.py`, `encrypted_records.py`, `privacy_vault.py`, `privacy_pipeline.py` | Envelope encryption, tokenization, identity restoration, cryptographic erasure        |
| `grant_delegation.py`                                                               | Seven-axis attenuation of delegated data access, with revocation propagation          |
| `evidence_notary.py`                                                                | Signed checkpoints and receipts                                                       |
| `review_queue.py`                                                                   | Bounded human review; overload never becomes approval                                 |
| `pack_floor.py`                                                                     | The kernel floor that no domain pack may weaken                                       |
| `education_models.py`                                                               | Honest, malicious, and Ollama models; honest and malicious routers                    |

The paper's figures (`evaluation/results/`) are generated separately and are not changed by
this package.
