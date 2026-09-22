# Provenance

trustkernel is a clean, standalone generalization of the `fssai-ra` reference implementation (*Trust by Construction*). It keeps the parts that make the argument runnable and removes everything tied to one domain or one paper.

## What was copied, and how

**The kernel, 20 modules, copied with mechanical renames only.** These are `accountable_action`, `custody_errors`, `delegation`, `disclosure`, `disclosure_sources`, `disclosure_store`, `encrypted_records`, `evidence`, `evidence_notary`, `exact_action`, `grant_delegation`, `key_custody`, `metrics`, `model_registry`, `pack_floor`, `privacy_pipeline`, `privacy_vault`, `profiles`, `review_queue` and `sql_backend`. The set is the import closure of the demonstration layer. The renames changed module paths, schema names and a handful of docstring examples. Two behavioural changes, both in `pack_floor.py`:

1. Failure tests are resolved against this repository's root, which is now explicit (`REPO_ROOT`, overridable via `repo_root=`), rather than two directories up from the module.
2. `credential`, `secret` and `pii` joined the protected-class markers. That can only protect more classes. No existing pack's classes contain the new markers, so no existing figure moves.

**The evaluation layer, generalized.** `falsification`, `delegation_eval`, `redteam`, `adaptive_attack` and the models module (now `agents`) had the education cast frozen into them: student ids, field names, grade states, the registrar. Every such reference now resolves through the world's `scenario` block. The test logic, the attempt order and the random-number consumption are unchanged. That's what makes exact reproduction possible.

**The world.** `EducationWorld` became `ScenarioWorld(world, controls)`. Its module constants (`STUDENTS`, `PEOPLE`, `AGENTS`, `RESOURCES`, `SOURCE_KEYS`, the injection pattern and the pack path) moved verbatim into `worlds/education/world.yaml`. Its methods are unchanged apart from reading the cast from the spec.

**Tests.** Every failure test the education pack names was ported, along with the kernel tests whose imports stayed inside the closure: delegation, composition and key secrecy, foundation security, privacy custody, and the adaptive attacker.

## What was left behind

The HTTP API and control plane, the Kafka, Redis, Iceberg and Spark backends, telemetry, federation, the data diode, the paper builders and their figure pipelines, the sector profiles, the console, and every paper, deck and audit artifact. None of these is imported by the demonstration layer. They would add surface without adding to the argument this repository makes.

## The equivalence evidence

`tests/reference/education_reference.json` was recorded from the reference implementation before any code was moved. `tests/test_reference_equivalence.py` requires the ported education world to reproduce it exactly:

- all 25 falsifiers: violation counts, and each attempt's verdict and denial code;
- all 29 ablation rows: enabled, disabled and restored violation counts, and the load-bearing verdict;
- all 33 delegation outcomes (10 hostile chains and 1 benign chain, × 3 arms), plus the 9-row delegation ablation;
- the 300-attack red team move by move, with all controls and with the execution mediator removed;
- the static, random and bandit adaptive tracks (episodes, forbidden outcomes, by-class, denial histograms), and the positive control.

The ported world uses different key material from the reference, since every seed is now namespaced by `world_id`. The reproduction is still exact, so no reported figure depends on which keys were used.
