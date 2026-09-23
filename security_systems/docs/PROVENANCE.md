# Provenance

trustkernel is a clean, standalone generalization of the `fssai-ra` reference implementation (*Trust by Construction*). It keeps the parts that make the argument runnable, removes everything tied to one domain or one paper, and adds a drop-in guard, three regulated-domain worlds, pack-derived contract tests, and a static world validator.

## What was copied, and how

**The kernel, 20 modules, copied with mechanical renames.** These are `accountable_action`, `custody_errors`, `delegation`, `disclosure`, `disclosure_sources`, `disclosure_store`, `encrypted_records`, `evidence`, `evidence_notary`, `exact_action`, `grant_delegation`, `key_custody`, `metrics`, `model_registry`, `pack_floor`, `privacy_pipeline`, `privacy_vault`, `profiles`, `review_queue` and `sql_backend`. The set is the import closure of the demonstration layer. Deliberate changes:

1. `pack_floor`: failure tests resolve against this repository's root (`REPO_ROOT`, overridable). `credential`, `secret` and `pii` joined the protected-class markers, which can only protect more classes.
2. `profiles`: `deployment_profile` is one of `reference`, `pilot`, or `hardware-isolated`.
3. Default key identifiers and docstrings use `reference` naming. Delegation environment variables use the `TRUSTKERNEL_` prefix.

**The evaluation layer, generalized.** `falsification`, `delegation_eval`, `redteam`, `adaptive_attack` and the agents module had one domain's cast frozen into them. Every such reference now resolves through the world's `scenario` block. Test logic, attempt order and random-number consumption are unchanged.

**The world.** The reference's world class became `ScenarioWorld(world, controls)`, with its cast moved to `worlds/<id>/world.yaml`.

## Equivalence, and why the reference world is gone

While generalizing, the original domain was first ported unchanged as a YAML world. It reproduced the reference implementation's recorded figures exactly, on different key material:

- all 25 falsifiers, attempt by attempt, including denial codes;
- all 29 ablation rows;
- all 33 delegation outcomes and the 9-row delegation ablation;
- the red team, move by move, with and without the execution mediator;
- every adaptive-attacker track and the positive control.

That world and its equivalence test were then removed at the author's direction, to keep this repository technical and domain-general. The evaluation modules haven't changed since the check passed, apart from reading the same values from YAML. The four current worlds pin their own figures in `evidence/`.

## What was left behind

The HTTP API and control plane, the Kafka, Redis, Iceberg and Spark backends, telemetry, federation, the data diode, the paper builders and figure pipelines, the sector profiles, the console, and every paper, deck and audit artifact.
