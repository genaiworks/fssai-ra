# Instructor guide — half-day tutorial (3.5 hours)

This extends the 90-minute lab (`INSTRUCTOR.md`) into the AI Con half-day tutorial. Module 2 *is* that lab, unchanged. Modules 1, 3 and 4 are instructor-led exercises built only on commands that already ship and already run offline. Use `README.md` as the participant handout for Module 2 and `docs/ADOPTION.md` as the worksheet for Module 4.

Preflight, sent a week ahead: `python -m pip install -e '.[dev]'`, then `python -m workshop.check --implementation starter` must print `2/7`. Nobody needs a model account, a GPU or network access in the room.

| Time | Module | What attendees do | Must see |
|---|---|---|---|
| 0–15 | Opening | Run `python examples/effect_oracle.py`; read the `write_then_reject` row | `refused: true` **and** `harmful_effect: true` in the same row |
| 15–60 | 1. Effect oracles and liveness | Wrap one of the example tools with `trustkernel.evaluation.observe_attempt`; write the harm predicate first, then the attack; add the paired legitimate call. Then run `python examples/replay_boundary.py` | Their own oracle catches write-then-deny; the legitimate write still passes; the forged retry is refused with `APPROVAL_SIGNATURE_INVALID` before the cache |
| 60–75 | Break | | |
| 75–165 | 2. Taint tracking lab | The 90-minute lab in `INSTRUCTOR.md`, with its checkpoints | `7/7` with both legitimate flows intact |
| 165–180 | Break | | |
| 180–200 | 3. Positive controls and ablation | `trustkernel falsify` (25/25); `trustkernel redteam --attempts 60 --remove execution_mediator` (the attacker wins); `trustkernel adaptive --budget 60 --prove-attacker`; then `trustkernel ablate --only F11 --only F13` | A zero is only trusted after the attacker wins against the weakened system; F11 and F13 each show two single removals with no harm and one joint removal where harm returns |
| 200–210 | 4. Port it | Copy `worlds/devtools` to a scratch directory, rename one agent and one tool, run `trustkernel check --world <path>` | `OK`, then the worksheet rows for their own system |

## Why F11 and F13

These are the ablation poll. Ask the room which controls can be deleted after the single removals, take a show of hands, then run the joint removals. Residency and model attestation each stop sensitive data being routed to a weaker model; proposal-digest binding and single-use approvals each stop replay. A single-removal study calls all four dead code. The joint removal shows they're backups.

## Timing and recovery

- Module 1 is the one most likely to overrun. If people are stuck at minute 45, hand out the four-row oracle from `examples/effect_oracle.py` and move on to the replay example.
- Module 3 commands take under a minute each on a laptop. `trustkernel matrix --attempts 300` takes about 35 seconds; run it on the projector rather than asking everyone to.
- If setup failed for someone, pair them. Every module runs from the same install.

## Claims to keep straight

Every number in the room comes from four synthetic policy worlds sharing one kernel and one attack grammar. The attack moves are authored, and the positive control shows they are strong enough to win against a weakened system. It doesn't show coverage of attacks nobody wrote. The timings in `evidence/guard-workloads.json` are warm, local, in-process reads without approval signing, so they aren't a deployment latency. Only machine execution of this plan has been rehearsed. Pilot it with a small group and adjust the minutes before claiming the timing works.
