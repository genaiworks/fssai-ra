# Repository map and source-reading guide

> **Documentation navigation:** [Documentation map](README.md) · [Start here](START_HERE.md) · [Glossary](GLOSSARY.md)
>
> **Recommended next:** Follow the [user guide](USER_GUIDE.md) for a walkthrough or the [research guide](RESEARCH_GUIDE.md) to record an experiment.

## Names and working directories

- **FSSAI-RA:** Fail-Secure Sovereign AI Reference Architecture, the project.
- **Trust by Construction / TBC:** the design approach and the name of the SDK package area.
- **`fssai-ra`:** repository name and inner application directory.
- **`fssaira`:** installed Python package and CLI executable.

Keep the current code paths stable when citing or extending the project. A local folder name does not require renaming the package, repository remote, or historical artifacts.

## Where to put and find things

| Location (relative to repository root) | Contents | Maintenance rule |
|---|---|---|
| `README.md` | Project front door | Keep short enough to orient a new reader |
| `publications/` | Paper register and reproduction template | One record per paper; software citation stays separate |
| `fssai-ra/docs/` | Maintained explanations and older provenance material | Link every artifact from the documentation map |
| `fssai-ra/src/fssaira/` | Runtime, CLI, experiments, adapters | State the boundary each component enforces |
| `fssai-ra/profiles/` | Synthetic domain profiles and SDK contracts | New profiles need their own evidence |
| `fssai-ra/contract/` | Requirements and bindings | Bind claims to real checks or explicit attestations |
| `fssai-ra/tests/` | Behavioral and artifact tests | Some historical tests require local manuscript archives |
| `fssai-ra/scripts/` | Demonstrations, verification, generators | Check whether a script writes tracked evidence before running |
| `fssai-ra/evaluation/results/` | Versioned component results | Snapshot evidence; regeneration is a deliberate change |
| `fssai-ra/audit/` | Historical audit logs, claims, and experiment outputs | Preserve provenance; use `work/` for fresh exploratory runs |
| `fssai-ra/challenges/`, `fssai-ra/threats/` | Adversary corpus and threat catalogue | Record authorship, fixtures, limits, and expected outcomes |
| `fssai-ra/conference/` | Education pack, attack lab, experiments | Historical path retained; tools are reusable across venues |
| `fssai-ra/paper/` | Retained manuscript versions and local drafts | Entire directory ignored and untracked; local files retained |
| `fssai-ra/console/` | React UI | Uses authenticated API; has no separate grant authority |
| `fssai-ra/deploy/` | Compose topology and environment example | Generated `.env` is local and untracked |
| `fssai-ra/adapters/`, `fssai-ra/jobs/` | Integration seams and analytics jobs | External-service requirements differ from the core demo |
| `fssai-ra/work/`, `work/` | Scratch outputs and experiments | Ignored; not a publication archive |
| `.github/` | CI and contribution templates | Distinguish runtime tests from paper-artifact validation |

## Read one mechanism end to end

1. Open `profiles/student_support.yaml` to understand policy vocabulary.
2. Read `src/fssaira/profiles.py` and `contract.py` for parsing and contract structure.
3. Read `control_plane.py`, `exact_action.py`, and `atomic_execution.py` for enforcement.
4. Read `evidence.py` and `decision_packet.py` for recorded evidence.
5. Read the matching tests before broadening a claim to another backend.

For the integrated local demonstration, start instead with `scripts/joined_demo.py` → `src/fssaira/joined_workflow.py` → `tests/test_joined_workflow.py`. This path is separate from the default HTTP control plane.

For the SDK, start with `profiles/tbc/` → `src/fssaira/tbc/contracts.py` → `runtime.py` → `client.py` → `tests/test_tbc_sdk.py`. Administrative operations and the model-facing dispatch boundary are deliberately different interfaces.

For data disclosure, follow `disclosure.py` → `disclosure_store.py` → `disclosure_api.py`, then [Governed disclosure](GOVERNED_DISCLOSURE.md). The opt-in privacy path adds its own configuration and limits.

## What is current, generated, or historical?

The user guide and feature catalogue describe reusable entry points. Versioned result JSON describes specific experimental snapshots. `audit/` logs describe runs on recorded hosts. Paper versions and speaker materials describe particular publication contexts. None should silently override the others.

Use `git ls-files` to see what a clean checkout includes. A local file's existence does not mean a reviewer receives it. In particular, historical `paper/tbc-v11` through later build dependencies may exist on an author's machine while being absent from Git.

When changing documentation, preserve old artifact paths where possible and explain their status. Do not delete submitted manuscripts or research evidence merely to reduce the visible file count.
